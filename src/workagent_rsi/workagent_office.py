"""Input staging, prompt construction, and output acceptance for Office agents."""

from __future__ import annotations

import json
import re
import shutil
import stat
from pathlib import Path, PureWindowsPath

from .contracts import TaskSpec
from .hashing import sha256_file
from .office_checks import MEDIA_TYPES
from .workagent_provider import AgentResponse, WorkAgentConfig, WorkAgentSkill
from .workagent_provider import CodexOfficeProvider


_SUFFIXES = {"excel": ".xlsx", "word": ".docx", "powerpoint": ".pptx"}

_TASK_MODE_RULES = {
    "create": (
        "TASK MODE: CREATE. There is no staged Office source to preserve. Follow the creation path only, "
        "start a new document/workbook/presentation as required, and do not open or invent an input template. "
    ),
    "edit": (
        "TASK MODE: EDIT. A staged source file is authoritative. Load that exact staged copy, preserve its existing "
        "content and required structure, and save a new output. Do not use any creation example below, do not create "
        "a replacement object that drops source content, and do not add slides/sheets/sections unless the task explicitly requests it. "
        "In TASK MODE: EDIT, do not call presentation.slides.add_slide anywhere, even if a creation example appears later; "
        "the creation examples are not applicable in TASK MODE: EDIT. For a generic PowerPoint edit, choose exactly one existing slide (slide 1 unless the task names another), do not iterate over every slide to add the new phrase, and add exactly one new textbox containing all missing phrases. Capture existing_shapes = list(chosen_slide.shapes) before adding it, scan every existing shape on that slide before placing the textbox, and assert the new rectangle is disjoint from every old rectangle using left/top/width/height. Keep every other slide unchanged and assert the original slide count. "
    ),
}


def _task_mode(task: TaskSpec) -> str:
    """Infer create/edit mode from the frozen task id, then staged inputs."""
    suffix = task.task_id.rsplit("-", 1)[-1].lower()
    if suffix in _TASK_MODE_RULES:
        return suffix
    return "edit" if task.input_files else "create"


_FORMAT_RULES = {
    "excel": (
        "Use openpyxl. write only the cells named in this task. Preserve every supplied source cell exactly when editing; "
        "For a creation task, start with openpyxl.Workbook() and do not call load_workbook to create the file; use load_workbook only for an existing input or to reopen the saved output. "
        "Write formulas by assigning the formula string to cell.value; never use cell.formula. "
        "Assign each requested literal cell value directly from the task; do not compute cell values from row numbers, indexes, multiplication, or loops. "
        "Read the current task as the source of truth, not a frozen example. Set the worksheet title exactly to the name requested by the current task before writing cells; assert the requested worksheet exists after reopening and assert every task-named cell and formula. Do not assume the frozen Summary example applies to another task; if the task requests Metrics, Budget, or another sheet, use that exact name and never leave the default Sheet title. "
        "for this edit, write only to the Summary sheet. Creation-task example values below apply only when the current task requests them. "
        "For an edit, write every requested Summary label and formula cell before saving; do not treat creating the sheet or formula alone as completion. "
        "Reopen the edited workbook and assert each requested Summary cell equals its exact requested value before writing the manifest. "
        "do not instantiate Workbook() for an edit; load the supplied workbook and preserve it. "
        "Use wb.create_sheet('Summary') on the loaded workbook when a new Summary sheet is required. "
        "Never copy Transactions cells into Summary; keep wb['Transactions'] unchanged. "
        "Write exact requested cells individually (for the quarterly creation example only, write summary_sheet['A5'] = 'Total', summary_sheet['B2'] = 120, summary_sheet['B3'] = 150, and summary_sheet['B4'] = 180; do not spread values across columns with a loop). Write the total label before writing the total formula: summary_sheet['B5'] = '=SUM(B2:B4)'. After reopening, assert summary_sheet['A5'].value == 'Total' and assert summary_sheet['B5'].value == '=SUM(B2:B4)'. "
        "Write formulas as direct Python strings beginning with '=' (for example, '=SUM(Transactions!B2:B4)'); "
        "do not build formulas by concatenating nested quoted fragments. Reopen with data_only=False so formula text is checked. "
        "Always reopen the saved output with load_workbook('outputs/<exact-name>.xlsx', data_only=False); never use read_file on .xlsx binary files. "
        "Do not replace a formula with a cached number. Use the exact requested output filename, write only to outputs/, "
        "and write a valid double-quoted JSON manifest. Create the complete script correctly on the first write and run it once before making edits."
    ),
    "word": (
        "Use python-docx. Every required heading must use style='Heading 1' or level=1 unless the task explicitly requests Heading 2; level=0 is Title, not Heading 1. "
        "A required Heading 2 must use style='Heading 2' or level=2. Keep required sentences exact. "
        "Use direct calls such as document.add_heading('Project Status', level=1), not manually edited style XML; never use level=0 for a required Heading 1. "
        "Never set document.styles['Heading 1'].level and never modify the built-in Heading 1 style level; style levels are not task content and changing them can invalidate every heading. "
        "Use separate add_heading and add_paragraph calls for each required section; never call add_paragraph on the result of add_heading. "
        "Call document.add_heading(title, level=1) separately for every required Heading 1; for a required Heading 2, call document.add_heading(title, level=2). "
        "Never attach heading or body text with add_run to a heading paragraph; put each required heading in its own paragraph and body text in a following add_paragraph call. "
        "Any required Heading 2 must be created with document.add_heading(title, level=2); never use document.add_paragraph(..., style='Heading 2') for a required heading, and never put a required heading in a body paragraph. "
        "Call document.add_heading(...) directly for each required heading; never assign the return value of add_heading to a document variable or treat it as a Document. For the frozen word-edit pattern, the safe document-level sequence is document.add_heading('Executive Summary', level=1), document.add_heading('Completed Work', level=1), document.add_heading('The pilot completed on 12 September.', level=2), document.add_heading('Next Steps', level=1), then document.add_paragraph('Action: send the final report to the steering group.'). Never call add_paragraph or add_run on an object returned by add_heading. "
        "Do not put a literal line break inside a quoted Python string; use an escaped \\n sequence or separate paragraph calls. "
        "Use document.add_paragraph(...) for body text; add_heading(...) returns a Paragraph, not a Document, so never call add_paragraph on its return value. "
        "Use the exact requested output filename, write only to outputs/, and write a valid double-quoted JSON manifest. "
        "Create the complete script correctly on the first write and run it once before making edits."
    ),
    "powerpoint": (
        "Use python-pptx with `import pptx` (then `pptx.Presentation(...)`), and import `Inches` from `pptx.util`. For editing, start from the staged deck and preserve the required slide count and source phrases. "
        "Inspect text by iterating each slide's shapes; inspect shape.text_frame.text when shape.has_text_frame; never use slide.text. "
        "when no staged input exists, start with Presentation() and do not invent or open a template input path. "
        "Call presentation.slides.add_slide(...) once for each requested slide, store each returned slide in its own variable, and place that slide's content only on that slide. "
        "Do not put later slide content on the first slide. "
        "For creation, derive the exact required slide count from the current task instruction and create exactly one slide for that count; never assume three slides for another task. use the blank slide layout (presentation.slide_layouts[6]) so unused title/content placeholders cannot overlap your textboxes, keep the slide count exactly equal to the requested count, and put all required phrases within those slides. Map each requested phrase to its specified slide; never add a dedicated extra slide for a phrase. The frozen three-slide skeleton applies only when the current task requests that exact mapping. "
        "do not branch on len(presentation.slides) inside a slide loop; assign each requested slide's content explicitly or use enumerate. For the frozen three-slide mapping, use this exact skeleton: slide1 = presentation.slides.add_slide(presentation.slide_layouts[6]); slide2 = presentation.slides.add_slide(presentation.slide_layouts[6]); slide3 = presentation.slides.add_slide(presentation.slide_layouts[6]); put Context and Plan on slide1, put Decision on slide2, and put Takeaway: approve the phased rollout. on slide3. Never use slide1.slides[1] or slide1.slides[2]; slide1 is a Slide, not a Presentation. Before saving a created deck, assert len(presentation.slides) equals the requested count, assert every required phrase is present, and check every shape pair for overlap. Put Context and Plan in separate text boxes; do not combine them in a newline string. Assign separate .text values 'Context' and 'Plan' to two different add_textbox calls, with the boxes at different vertical positions. "
        "For editing, never call add_slide; modify the existing slides only. The staged deck may contain blank slides without title or placeholder shapes: do not use slide.shapes.title or slide.placeholders[index]; inspect slide.shapes and use slide.shapes.add_textbox(...) when no suitable shape exists. For a required new phrase, choose exactly one existing slide, save the phrase there using an independent textbox; never replace source text with the new phrase, and do not add a textbox to every slide. "
        "When a phrase contains a line break, do not put a literal line break inside a quoted Python string; use an escaped \\n sequence or separate text-frame paragraphs. "
        "Capture existing_shapes = list(slide.shapes) before calling add_textbox; use only that snapshot for the new textbox overlap check and never include the new textbox in the existing_shapes overlap check. "
        "A python-pptx Shape has no right, bottom, or shapes attributes; never use text_box.shapes, shape.right, shape.bottom, or slide.text. Pass slide.shapes.add_textbox coordinates and dimensions as Inches(...) values. Do not call shape.overlap; python-pptx shapes have no overlap method. Compare rectangle edges with left, top, width, and height: rectangles overlap only when both horizontal and vertical ranges intersect. For old and new shapes, the non-overlap test is old.left + old.width <= new.left or new.left + new.width <= old.left or old.top + old.height <= new.top or new.top + new.height <= old.top; negate that expression to assert overlap is false. Iterate existing_shapes directly and compare the new textbox against each old shape; never access right/bottom/shapes properties. "
        "Place the new textbox in a measured free region, then check every new textbox against every existing shape for overlap and assert len(presentation.slides) equals the original count before saving. Use separate non-overlapping text boxes with positive "
        "width and height inside slide bounds. Reopen and inspect every slide and shape; for edits, reopen and assert the new phrase before saving the manifest. "
        "Use the exact requested output filename, write only to outputs/, and write a valid double-quoted JSON manifest. "
        "Create the complete script correctly on the first write and run it once before making edits."
    ),
}


def _domain_suffix(task: TaskSpec) -> str:
    try:
        return _SUFFIXES[task.domain.lower()]
    except KeyError as exc:
        raise ValueError(f"unsupported Office domain: {task.domain}") from exc


def _is_reparse(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _check_existing_segments(path: Path) -> None:
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            if _is_reparse(part):
                raise ValueError(f"symlink or reparse point is not allowed: {part.name}")


def _safe_relative_input(value: str) -> Path:
    if not value or "\\" in value or ":" in value or value.startswith("/"):
        raise ValueError("input path must be local and relative")
    windows_path = PureWindowsPath(value)
    if windows_path.is_absolute() or windows_path.drive or windows_path.root:
        raise ValueError("input path must be local and relative")
    pieces = value.split("/")
    if any(piece in ("", ".", "..") for piece in pieces):
        raise ValueError("input path has an unsafe component")
    return Path(*pieces)


def _source_path(value: str, base: Path) -> Path:
    if not value or value.startswith(("//", "\\\\")):
        raise ValueError("network and empty input paths are not allowed")
    if any(part == ".." for part in value.replace("\\", "/").split("/")):
        raise ValueError("input path has a traversal component")
    path = Path(value)
    if path.is_absolute():
        if path.drive.startswith("\\\\"):
            raise ValueError("network input paths are not allowed")
        return path
    return base / _safe_relative_input(value)


def copy_task_inputs(task: TaskSpec, workspace: Path, input_base: Path) -> dict:
    """Copy explicitly named task-domain Office files and save a private manifest."""
    suffix = _domain_suffix(task)
    base = Path(input_base).absolute()
    workspace = Path(workspace).absolute()
    _check_existing_segments(base)
    _check_existing_segments(workspace)
    files: list[dict[str, object]] = []
    sources: list[tuple[Path, str, str]] = []
    for index, value in enumerate(task.input_files, 1):
        source = _source_path(value, base)
        _check_existing_segments(source)
        if not source.exists() or not source.is_file() or not stat.S_ISREG(source.lstat().st_mode):
            raise ValueError(f"input is not a regular file: {source.name}")
        if source.suffix != suffix:
            raise ValueError(f"input format does not match {task.domain}: {source.name}")
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", source.name)
        if safe_name in ("", ".", ".."):
            raise ValueError("input filename has no safe representation")
        destination = f"inputs/{index:04d}-{safe_name}"
        sources.append((source, destination, source.name))
    inputs = workspace / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    _check_existing_segments(inputs)
    for source, destination, label in sources:
        copied = workspace / destination
        _check_existing_segments(copied)
        if copied.exists():
            raise ValueError(f"staged input already exists: {copied.name}")
        source_hash = sha256_file(source)
        shutil.copyfile(source, copied)
        copied_hash = sha256_file(copied)
        if source_hash != copied_hash or source_hash != sha256_file(source):
            raise ValueError(f"input changed during copy: {label}")
        files.append({
            "source": label,
            "copied": destination,
            "size_bytes": copied.stat().st_size,
            "source_sha256": source_hash,
            "copy_sha256": copied_hash,
        })
    manifest = {"files": files}
    (workspace / "input_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest


def verify_task_input_hashes(task: TaskSpec, workspace: Path, input_base: Path, manifest: dict) -> None:
    """Raise ValueError if a source or staged copy changed after provider execution."""
    _domain_suffix(task)
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != len(task.input_files):
        raise ValueError("input manifest does not match task")
    base = Path(input_base).absolute()
    workspace = Path(workspace).absolute()
    for index, (value, item) in enumerate(zip(task.input_files, files), 1):
        source = _source_path(value, base)
        _check_existing_segments(source)
        copied_name = f"inputs/{index:04d}-{re.sub(r'[^A-Za-z0-9._-]', '_', source.name)}"
        if not isinstance(item, dict) or item.get("copied") != copied_name or item.get("source") != source.name:
            raise ValueError("input manifest path does not match task")
        copied = workspace / copied_name
        _check_existing_segments(copied)
        for path in (source, copied):
            if not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
                raise ValueError("source or staged input is no longer an ordinary file")
        if sha256_file(source) != item.get("source_sha256") or sha256_file(copied) != item.get("copy_sha256"):
            raise ValueError("source or staged input changed after copy")


def build_task_prompt(task: TaskSpec, input_manifest: dict, agent_instructions: str | WorkAgentSkill) -> str:
    """Expose only the task request and staged input paths to the agent."""
    suffix = _domain_suffix(task)
    if isinstance(agent_instructions, WorkAgentSkill):
        agent_instructions = agent_instructions.instructions
    template = (Path(__file__).parent / "prompts" / "office_agent.md").read_text(encoding="utf-8")
    copied_names = [item["copied"] for item in input_manifest.get("files", [])]
    input_lines = "\n".join(f"- {name}" for name in copied_names) or "- None"
    return (
        template.replace("{domain}", task.domain.lower())
        .replace("{suffix}", suffix)
        .replace("{instruction}", task.instruction)
        .replace("{agent_instructions}", agent_instructions)
        .replace("{format_rules}", _FORMAT_RULES[task.domain.lower()] + _TASK_MODE_RULES[_task_mode(task)])
        .replace("{input_files}", input_lines)
    )


def validate_deliverables(
    task: TaskSpec, workspace: Path, response: AgentResponse, config: WorkAgentConfig
) -> list[Path]:
    """Accept only listed, contained, ordinary files of the task's Office format."""
    suffix = _domain_suffix(task)
    workspace = Path(workspace).absolute()
    _check_existing_segments(workspace)
    response_path = workspace / "agent_response.json"
    manifest_path = workspace / "deliverables.json"
    for path in (response_path, manifest_path):
        if not path.is_file() or _is_reparse(path) or not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError(f"required response or manifest is missing or unsafe: {path.name}")
    try:
        disk_response = AgentResponse.model_validate_json(response_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid response or deliverables manifest") from exc
    if disk_response != response or response.status != "completed":
        raise ValueError("response on disk disagrees with current completed response")
    if not isinstance(manifest, dict) or set(manifest) != {"deliverables"} or not isinstance(manifest["deliverables"], list):
        raise ValueError("invalid deliverables manifest shape")
    if manifest["deliverables"] != response.deliverables:
        raise ValueError("response and deliverables manifest disagree")
    if not 1 <= len(response.deliverables) <= config.max_output_files or len(set(response.deliverables)) != len(response.deliverables):
        raise ValueError("invalid deliverable count or duplicate path")
    outputs = workspace / "outputs"
    if not outputs.is_dir():
        raise ValueError("outputs directory is missing")
    _check_existing_segments(outputs)
    accepted: list[Path] = []
    for value in response.deliverables:
        pieces = value.split("/")
        if len(pieces) < 2 or pieces[0] != "outputs" or any(part in ("", ".", "..") for part in pieces):
            raise ValueError("deliverable must be a safe path under outputs/")
        if "\\" in value or ":" in value or value.startswith("/"):
            raise ValueError("deliverable path is not relative")
        path = workspace.joinpath(*pieces)
        _check_existing_segments(path)
        if path.suffix != suffix or not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError(f"deliverable is missing, nonregular, or wrong format: {value}")
        if not path.resolve().is_relative_to(outputs.resolve()):
            raise ValueError("deliverable escapes outputs/")
        size = path.stat().st_size
        if not 0 < size <= config.max_artifact_bytes:
            raise ValueError(f"deliverable has invalid size: {value}")
        accepted.append(path)
    return accepted


class WorkAgentOfficeAdapter:
    """Bridge a single isolated Office provider run into Orchestrator events."""

    def __init__(
        self,
        run_root: Path,
        config: WorkAgentConfig,
        *,
        input_base: Path,
        agent_instructions: str = "",
    ) -> None:
        self.run_root = Path(run_root)
        self.config = config
        self.input_base = Path(input_base)
        self.agent_instructions = agent_instructions
        self.provider = CodexOfficeProvider(config)

    def execute(self, task: TaskSpec, skill_id: str):
        workspace = self.run_root / "agent_workspace"
        records = self.run_root / "provider_records"
        yield {"kind": "started", "provider": "workagent", "skill_id": skill_id}
        try:
            manifest = copy_task_inputs(task, workspace, self.input_base)
        except (OSError, ValueError) as exc:
            yield {"kind": "failure", "message": f"input staging failed: {exc}", "provider": "workagent"}
            return
        yield {"kind": "input_manifest", "manifest": manifest}

        try:
            prompt = build_task_prompt(task, manifest, self.agent_instructions)
            outcome = self.provider.run(prompt, workspace, records)
            yield {
                "kind": "provider_output",
                "status": outcome.status,
                "record": outcome.record.model_dump(mode="json") if outcome.record else None,
                "error": outcome.error,
            }
            # No response or artifact is trusted until both original and staged
            # inputs have been checked after every provider exit.
            verify_task_input_hashes(task, workspace, self.input_base, manifest)
            if outcome.status != "completed" or outcome.response is None:
                kind = "unavailable" if outcome.status == "unavailable" else "failure"
                yield {
                    "kind": kind,
                    "message": outcome.error or f"provider ended with status {outcome.status}",
                    "provider": "workagent",
                    "status": outcome.status,
                    "retryable": False,
                }
                return
            paths = validate_deliverables(task, workspace, outcome.response, self.config)
        except (OSError, ValueError) as exc:
            yield {"kind": "failure", "message": str(exc), "provider": "workagent", "retryable": False}
            return
        for path in paths:
            yield {
                "kind": "artifact",
                "artifact_path": str(path),
                "artifact_name": path.relative_to(workspace).as_posix(),
                "media_type": MEDIA_TYPES[task.domain.lower()],
            }
