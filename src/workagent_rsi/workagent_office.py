"""Input staging, prompt construction, and output acceptance for Office agents."""

from __future__ import annotations

import json
import re
import shutil
import stat
from pathlib import Path, PureWindowsPath

from .contracts import TaskSpec
from .hashing import sha256_file
from .workagent_provider import AgentResponse, WorkAgentConfig


_SUFFIXES = {"excel": ".xlsx", "word": ".docx", "powerpoint": ".pptx"}


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
        relative = _safe_relative_input(value)
        source = base / relative
        _check_existing_segments(source)
        if not source.exists() or not source.is_file() or not stat.S_ISREG(source.lstat().st_mode):
            raise ValueError(f"input is not a regular file: {relative.name}")
        if source.suffix != suffix:
            raise ValueError(f"input format does not match {task.domain}: {relative.name}")
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
        relative = _safe_relative_input(value)
        source = base / relative
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


def build_task_prompt(task: TaskSpec, input_manifest: dict, agent_instructions: str) -> str:
    """Expose only the task request and staged input paths to the agent."""
    suffix = _domain_suffix(task)
    template = (Path(__file__).parent / "prompts" / "office_agent.md").read_text(encoding="utf-8")
    copied_names = [item["copied"] for item in input_manifest.get("files", [])]
    input_lines = "\n".join(f"- {name}" for name in copied_names) or "- None"
    return (
        template.replace("{domain}", task.domain.lower())
        .replace("{suffix}", suffix)
        .replace("{instruction}", task.instruction)
        .replace("{agent_instructions}", agent_instructions)
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
