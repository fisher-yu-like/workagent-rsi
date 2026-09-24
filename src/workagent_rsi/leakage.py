from __future__ import annotations

import re
from pathlib import PurePosixPath

from .rsi_contracts import CandidatePatch


class LeakageCritic:
    def __init__(self, protected_values: list[str] | None = None, protected_paths: list[str] | None = None) -> None:
        self.protected_values = [value for value in (protected_values or []) if value]
        self.protected_paths = {PurePosixPath(path).name.lower() for path in (protected_paths or [])}

    def scan(self, candidate: CandidatePatch) -> list[str]:
        findings: list[str] = []
        for edit in candidate.atomic_edits:
            target_name = PurePosixPath(edit.target_path).name.lower()
            patch_lower = edit.patch.lower()
            if target_name in self.protected_paths or any(
                token in target_name for token in ("evaluator", "promotion", "registry", "hidden", "allowlist")
            ):
                findings.append(f"protected target path: {edit.target_path}")
            for value in self.protected_values:
                if value.lower() in patch_lower:
                    findings.append("protected value appears in candidate patch")
                    break
            if any(token in patch_lower for token in ("import subprocess", "os.system", "powershell", "invoke-webrequest", "requests.get", "socket.")):
                findings.append("unapproved execution or network capability")
            if re.search(r"p3-task-\d+\s*[\"']?\s*:", patch_lower):
                findings.append("task-specific answer mapping")
        return sorted(set(findings))
