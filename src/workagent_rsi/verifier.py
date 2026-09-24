from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .hashing import canonical_json_hash
from .leakage import LeakageCritic
from .rsi_contracts import CandidatePatch, VerificationReport


Runner = Callable[[list[str], Path, int], subprocess.CompletedProcess[str]]


def _run(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, timeout=timeout, capture_output=True, text=True, check=False)


class VerificationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed_targets: set[str]
    protected_paths: set[str] = Field(default_factory=set)
    protected_values: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=120, ge=1)


class CandidateVerifier:
    def __init__(self, runner: Runner = _run) -> None:
        self.runner = runner

    def verify(
        self,
        candidate: CandidatePatch,
        workspace: str | Path,
        policy: VerificationPolicy,
    ) -> VerificationReport:
        root = Path(workspace)
        checks: list[str] = ["path_policy"]
        violations: list[str] = []
        warnings: list[str] = []
        test_results: dict[str, object] = {}

        for edit in candidate.atomic_edits:
            if edit.target_path not in policy.allowed_targets:
                violations.append(f"target not allowlisted: {edit.target_path}")
            if edit.target_path in policy.protected_paths:
                violations.append(f"protected target: {edit.target_path}")
        if violations:
            return self._report(candidate, checks, violations, warnings, test_results)

        checks.append("leakage")
        violations.extend(LeakageCritic(policy.protected_values, list(policy.protected_paths)).scan(candidate))
        if violations:
            return self._report(candidate, checks, violations, warnings, test_results)

        checks.append("patch_schema")
        for edit in candidate.atomic_edits:
            try:
                payload = json.loads(edit.patch)
                if not isinstance(payload, dict):
                    raise ValueError("patch JSON must be an object")
            except (json.JSONDecodeError, ValueError) as exc:
                violations.append(f"invalid patch JSON: {exc}")
        if violations:
            return self._report(candidate, checks, violations, warnings, test_results)

        checks.append("compile")
        completed = self.runner(["py", "-3.12", "-m", "compileall", "-q", str(root)], root, policy.timeout_seconds)
        test_results["compile_exit_code"] = completed.returncode
        if completed.returncode != 0:
            violations.append("candidate workspace compilation failed")
            return self._report(candidate, checks, violations, warnings, test_results)

        tests_dir = root / "tests"
        if tests_dir.is_dir():
            checks.append("pytest")
            completed = self.runner(
                ["py", "-3.12", "-m", "pytest", "-q", str(tests_dir)], root, policy.timeout_seconds
            )
            test_results["pytest_exit_code"] = completed.returncode
            if completed.returncode != 0:
                violations.append("candidate tests failed")
        else:
            warnings.append("candidate workspace has no candidate-authored tests")
        return self._report(candidate, checks, violations, warnings, test_results)

    @staticmethod
    def _report(
        candidate: CandidatePatch,
        checks: list[str],
        violations: list[str],
        warnings: list[str],
        test_results: dict[str, object],
    ) -> VerificationReport:
        evidence = canonical_json_hash(
            {
                "candidate": candidate.model_dump(mode="json"),
                "checks": checks,
                "violations": violations,
                "warnings": warnings,
                "test_results": test_results,
            }
        )
        return VerificationReport(
            candidate_id=candidate.candidate_id,
            passed=not violations,
            critical_violations=violations,
            warnings=warnings,
            executed_checks=checks,
            test_results=test_results,
            artifact_results={},
            evidence_refs=[evidence],
        )
