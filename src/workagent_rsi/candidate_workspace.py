from __future__ import annotations

import shutil
import subprocess
import os
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict

from .hashing import sha256_file
from .view_safety import checked_path, relative_reference, ordinary_file


PROTECTED_BASENAMES = {
    "evaluator.py",
    "frozen_evaluator.py",
    "hidden.jsonl",
    "hidden_tasks.jsonl",
    "promotion.py",
    "registry.db",
    "com_validation.json",
}
PROTECTED_SEGMENTS = {'.git', '.planning', '.ssh', '.aws', '.codex', '.config', '__pycache__',
                      'project_artifacts', 'results', 'provider_records', 'assessment', 'tests',
                      'hidden', 'regression', 'ood', 'final_test', 'promotion_validation', 'credentials'}


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
        source = checked_path(source_root)
        destination = checked_path(workspace_root)
        if source == destination or not source.is_dir():
            raise ValueError('candidate source and destination must be distinct directories')
        if destination.exists() and any(destination.iterdir()):
            raise ValueError("candidate workspace must be empty")
        planned = []
        names = {'agents.md', '.git'}
        for relative in allowed_files:
            safe = self._safe_relative(relative)
            if self._protected(safe):
                raise ValueError(f"protected candidate file: {relative}")
            source_path = ordinary_file(source / Path(*safe.parts))
            planned.append((relative, source_path, None))
        for relative, content in context_files.items():
            safe = self._safe_relative(relative)
            if self._protected(safe):
                raise ValueError(f"protected context file: {relative}")
            if not isinstance(content, str):
                raise ValueError('candidate context must be authored text')
            planned.append((relative, None, content))
        for relative, _, _ in planned:
            name = relative.casefold()
            if name in names or any(name.startswith(n+'/') or n.startswith(name+'/') for n in names):
                raise ValueError('candidate file collision or reserved workspace policy path')
            names.add(name)
        excluded = self._discover_protected(source)
        destination.mkdir(parents=True, exist_ok=True)
        for relative, source_path, content in planned:
            target = checked_path(destination / relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            if source_path is not None:
                digest = sha256_file(ordinary_file(source_path))
                shutil.copyfile(source_path, target)
                if sha256_file(source_path) != digest or sha256_file(target) != digest:
                    raise ValueError('candidate source changed during export')
            else:
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
        return relative_reference(value)

    @staticmethod
    def _protected(path: PurePosixPath) -> bool:
        return (path.name.lower() in PROTECTED_BASENAMES or path.name.lower() == '.env'
                or path.suffix.lower() in {'.db', '.sqlite', '.sqlite3'}
                or any(part.lower() in PROTECTED_SEGMENTS for part in path.parts))

    @staticmethod
    def _discover_protected(source: Path) -> list[str]:
        protected = []
        for directory, folders, files in os.walk(source, followlinks=False):
            safe_folders = []
            for name in folders:
                try:
                    checked_path(Path(directory) / name)
                    if name != '.git': safe_folders.append(name)
                except ValueError:
                    pass
            folders[:] = safe_folders
            protected.extend((Path(directory)/name).relative_to(source).as_posix()
                             for name in files if name.lower() in PROTECTED_BASENAMES)
        return sorted(protected)
