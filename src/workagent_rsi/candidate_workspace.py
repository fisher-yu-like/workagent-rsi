from __future__ import annotations

import shutil
import subprocess
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict

from .hashing import sha256_file


PROTECTED_BASENAMES = {
    "evaluator.py",
    "frozen_evaluator.py",
    "hidden.jsonl",
    "hidden_tasks.jsonl",
    "promotion.py",
    "registry.db",
    "com_validation.json",
}


class CandidateWorkspaceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root: str
    file_hashes: dict[str, str]
    excluded_protected_paths: list[str]


class CandidateWorkspaceBuilder:
    POLICY = """# Candidate Workspace Policy

- Edit only files already present in this workspace.
- Do not access parent directories, hidden tasks, evaluators, governance policy, credentials, or historical evidence.
- Return a structured candidate patch; do not deploy or modify the source repository.
- Do not add network, subprocess, or unrestricted filesystem access.
"""

    def export(
        self,
        source_root: str | Path,
        workspace_root: str | Path,
        allowed_files: list[str],
        context_files: dict[str, str],
    ) -> CandidateWorkspaceManifest:
        source = Path(source_root).resolve()
        destination = Path(workspace_root)
        if destination.exists() and any(destination.iterdir()):
            raise ValueError("candidate workspace must be empty")
        destination.mkdir(parents=True, exist_ok=True)

        excluded = self._discover_protected(source)
        for relative in allowed_files:
            safe = self._safe_relative(relative)
            if safe.name.lower() in PROTECTED_BASENAMES:
                raise ValueError(f"protected candidate file: {relative}")
            source_path = (source / Path(*safe.parts)).resolve()
            if source not in source_path.parents and source_path != source:
                raise ValueError("candidate file must remain relative to source root")
            if source_path.is_symlink() or not source_path.is_file():
                raise ValueError(f"candidate source file unavailable: {relative}")
            target = destination / Path(*safe.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, target)

        for relative, content in context_files.items():
            safe = self._safe_relative(relative)
            if safe.name.lower() in PROTECTED_BASENAMES:
                raise ValueError(f"protected context file: {relative}")
            target = destination / Path(*safe.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")

        (destination / "AGENTS.md").write_text(self.POLICY, encoding="utf-8", newline="\n")
        subprocess.run(["git", "init", "-q"], cwd=destination, check=True, capture_output=True, text=True)
        subprocess.run(["git", "add", "."], cwd=destination, check=True, capture_output=True, text=True)
        file_hashes = {
            path.relative_to(destination).as_posix(): sha256_file(path)
            for path in sorted(destination.rglob("*"))
            if path.is_file() and ".git" not in path.parts
        }
        return CandidateWorkspaceManifest(
            root=str(destination.resolve()),
            file_hashes=file_hashes,
            excluded_protected_paths=excluded,
        )

    @staticmethod
    def _safe_relative(value: str) -> PurePosixPath:
        if "\\" in value or ":" in value:
            raise ValueError("candidate paths must be relative POSIX paths")
        path = PurePosixPath(value)
        if path.is_absolute() or not value or ".." in path.parts or value == ".":
            raise ValueError("candidate paths must be relative to the workspace")
        return path

    @staticmethod
    def _discover_protected(source: Path) -> list[str]:
        return sorted(
            path.relative_to(source).as_posix()
            for path in source.rglob("*")
            if path.is_file() and path.name.lower() in PROTECTED_BASENAMES
        )
