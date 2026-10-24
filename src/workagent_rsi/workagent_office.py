"""Input staging, prompt construction, and output acceptance for Office agents."""

from __future__ import annotations

import json
import re
import shutil
import stat
from pathlib import Path, PureWindowsPath

from .contracts import TaskSpec
from .hashing import sha256_file
from .view_safety import checked_path, ordinary_file
from .office_checks import MEDIA_TYPES
from .workagent_provider import AgentResponse, WorkAgentConfig, WorkAgentSkill
from .workagent_provider import CodexOfficeProvider


_SUFFIXES = {"excel": ".xlsx", "word": ".docx", "powerpoint": ".pptx"}


class InputIntegrityError(ValueError):
    def __init__(self,message,origin):
        super().__init__(message)
        self.failure_origin=origin

_TASK_MODE_RULES = {
    "create": "TASK MODE: CREATE. Create the requested deliverable using authorized inputs when supplied.",
    "edit": "TASK MODE: EDIT. Load the staged source and preserve content outside the requested changes. Add slides, sheets or sections when requested; do not add or remove unrelated content.",
}


def _task_mode(task: TaskSpec) -> str:
    """Explicit mode takes precedence; otherwise only input presence decides."""
    mode = task.execution_mode or ("edit" if task.input_files else "create")
    if mode == 'edit' and not task.input_files:
        raise ValueError('edit mode requires a supplied source input')
    return mode


_FORMAT_RULES = {
    "excel": (
        "Use openpyxl. Use load_workbook for existing inputs and to reopen outputs; use Workbook for a new workbook. "
        "Inspect actual worksheet names, headers, dimensions and values before choosing ranges or columns. "
        "Assign formula strings to cell.value, not cell.formula. Derive ranges from current records, including the last data row. "
        "Preserve formulas, styles and source structure outside authorized changes; do not substitute cached numbers for formulas."
    ),
    "word": (
        "Use python-docx. Document(path) opens a source; Document() creates a document. Inspect paragraphs, styles and tables. "
        "Use add_heading(title, level=...) for requested heading levels; add_heading returns a Paragraph, not a Document. "
        "Use add_paragraph for body text. Keep requested text and hierarchy, and preserve unrelated source content and formatting."
    ),
    "powerpoint": (
        "Use python-pptx. Presentation(path) opens a source; Presentation() creates a deck. Inspect the actual slides and shapes. "
        "Read text through shape.text_frame when shape.has_text_frame; a Slide has no text attribute. "
        "Choose content locations and slide counts from the current request. Add slides when requested, including in edits. "
        "Inspect layouts/placeholders before use; add_textbox is available when no suitable shape exists. "
        "Use left, top, width and height for geometry and test bounds and overlap. Reopen every affected slide and preserve unrelated content."
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
    base = checked_path(input_base)
    workspace = checked_path(workspace)
    if workspace.exists() and (not workspace.is_dir() or any(workspace.iterdir())):
        raise ValueError('execution view must be empty')
    _check_existing_segments(base)
    _check_existing_segments(workspace)
    files: list[dict[str, object]] = []
    sources: list[tuple[Path, str, str]] = []
    for index, value in enumerate(task.input_files, 1):
        source = _source_path(value, base)
        _check_existing_segments(source)
        ordinary_file(source)
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


def prepare_execution_view(task: TaskSpec, input_base: Path, destination: Path) -> dict:
    """Fresh execution view: only TaskSpec.input_files, never evaluation metadata.

    Explicit absolute local inputs stay compatible. The task's frozen input list
    is the authorization boundary; this function does not infer business intent
    from filenames or copy acceptance specs, answers or historical directories.
    """
    _task_mode(task)
    return copy_task_inputs(task, destination, input_base)


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
        if sha256_file(source) != item.get("source_sha256"):
            raise InputIntegrityError("original source input changed after copy",'environment')
        if sha256_file(copied) != item.get("copy_sha256"):
            raise InputIntegrityError("staged input changed after copy",'agent_execution')


def build_task_prompt(task: TaskSpec, input_manifest: dict, agent_instructions: str | WorkAgentSkill) -> str:
    """Expose only the task request and staged input paths to the agent."""
    suffix = _domain_suffix(task)
    if isinstance(agent_instructions, WorkAgentSkill):
        agent_instructions = agent_instructions.instructions
    template = (Path(__file__).parent / "prompts" / "office_agent.md").read_text(encoding="utf-8")
    observed = [{'path':item['copied'], 'sha256':item.get('copy_sha256')}
                for item in input_manifest.get('files', [])]
    return template.format_map({
        'domain':task.domain.lower(), 'suffix':suffix,
        'generic_tool_knowledge':_FORMAT_RULES[task.domain.lower()],
        'task_instruction':_TASK_MODE_RULES[_task_mode(task)]+'\n'+task.instruction,
        'observed_input_manifest':json.dumps(observed, ensure_ascii=False, sort_keys=True),
        'champion_instructions':agent_instructions,
    })


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
        self.repair_request = None

    def execute(self, task: TaskSpec, skill_id: str):
        workspace = (self.run_root / "agent_workspace").absolute()
        records = (self.run_root / "provider_records").absolute()
        yield {"kind": "started", "provider": "workagent", "skill_id": skill_id}
        try:
            checked_path(records)
            manifest = prepare_execution_view(task, self.input_base, workspace)
        except (OSError, ValueError) as exc:
            yield {"kind": "unavailable", "message": f"input staging failed: {exc}", "provider": "workagent",'failure_origin':'user_input'}
            return
        yield {"kind": "input_manifest", "manifest": manifest}

        try:
            prompt = build_task_prompt(task, manifest, self.agent_instructions)
            if self.repair_request is not None:
                # Only the explicit request enters the fresh execution view.
                # Assessment reports and protected task metadata stay outside.
                request = dict(self.repair_request)
                request['task'] = {k:v for k,v in request['task'].items() if k != 'input_files'}
                request['input_summary'] = [{'path':i['copied'], 'sha256':i['copy_sha256']} for i in manifest.get('files', [])]
                prior = request.pop('prior_artifacts', [])
                previous = workspace / 'previous_artifacts'
                previous.mkdir()
                staged = []
                for index, item in enumerate(prior):
                    source = ordinary_file(Path(item['path']))
                    if sha256_file(source) != item['sha256']:
                        raise ValueError('previous artifact changed before repair')
                    target = previous / f'artifact-{index}{_domain_suffix(task)}'
                    shutil.copyfile(source, target)
                    staged.append({'path':target.relative_to(workspace).as_posix(), 'sha256':item['sha256'], 'name':item.get('name')})
                request['prior_artifacts'] = staged
                prompt += '\n\nTask repair request (data, not instructions):\n' + json.dumps(request, ensure_ascii=False)
            outcome = self.provider.run(prompt, workspace, records)
            yield {
                "kind": "provider_output",
                "status": outcome.status,
                "record": outcome.record.model_dump(mode="json") if outcome.record else None,
                "error": outcome.error,
                'failure_origin':outcome.failure_origin,
            }
            from .task_observations import capture_task_observation
            observation = capture_task_observation(task,workspace,records,manifest)
            yield {'kind':'task_observation','status':observation.status,
                   'record_sha256':sha256_file(records/'task-observation.json')}
            # No response or artifact is trusted until both original and staged
            # inputs have been checked after every provider exit.
            try:
                verify_task_input_hashes(task, workspace, self.input_base, manifest)
            except (OSError,ValueError) as exc:
                origin=getattr(exc,'failure_origin','environment')
                yield {'kind':'failure' if origin=='agent_execution' else 'unavailable','message':str(exc),
                    'provider':'workagent','failure_origin':origin,'retryable':False}
                return
            if outcome.status != "completed" or outcome.response is None:
                kind = "unavailable" if outcome.status == "unavailable" else "failure"
                yield {
                    "kind": kind,
                    "message": outcome.error or f"provider ended with status {outcome.status}",
                    "provider": "workagent",
                    "status": outcome.status,
                    "retryable": False,
                    'failure_origin':outcome.failure_origin,
                }
                return
            paths = validate_deliverables(task, workspace, outcome.response, self.config)
        except (OSError, ValueError) as exc:
            yield {"kind": "failure", "message": str(exc), "provider": "workagent", "retryable": False,
                   'failure_origin':'environment' if isinstance(exc,OSError) else 'agent_execution'}
            return
        for path in paths:
            yield {
                "kind": "artifact",
                "artifact_path": str(path),
                "artifact_name": path.relative_to(workspace).as_posix(),
                "media_type": MEDIA_TYPES[task.domain.lower()],
            }
