from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .hashing import canonical_json_hash, sha256_file
from .rsi_contracts import AtomicEdit, CandidatePatch, FailureDiagnosis, ProviderRecord


Runner = Callable[[list[str], Path, int], subprocess.CompletedProcess[str]]


class CandidateProvider(Protocol):
    def generate(
        self,
        workspace: str | Path,
        diagnoses: Sequence[FailureDiagnosis],
        parent_version: str,
        edit_budget: int,
        record_root: str | Path,
    ) -> tuple[CandidatePatch | None, ProviderRecord]: ...


def _workspace_hash(workspace: Path) -> str:
    hashes = {
        path.relative_to(workspace).as_posix(): sha256_file(path)
        for path in sorted(workspace.rglob("*"))
        if path.is_file() and ".git" not in path.parts and "provider_records" not in path.parts
    }
    return canonical_json_hash(hashes)


def _default_runner(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, timeout=timeout, capture_output=True, text=True, check=False)


class CodexCandidateProvider:
    def __init__(
        self,
        schema_path: str | Path,
        provider_version: str,
        *,
        executable: str = "codex",
        timeout_seconds: int = 180,
        runner: Runner = _default_runner,
    ) -> None:
        self.schema_path = Path(schema_path).resolve()
        self.provider_version = provider_version
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self.runner = runner

    def generate(
        self,
        workspace: str | Path,
        diagnoses: Sequence[FailureDiagnosis],
        parent_version: str,
        edit_budget: int,
        record_root: str | Path,
    ) -> tuple[CandidatePatch | None, ProviderRecord]:
        workspace_path = Path(workspace).resolve()
        records = Path(record_root)
        records.mkdir(parents=True, exist_ok=True)
        output_path = records / "candidate.json"
        stdout_path = records / "provider.stdout.jsonl"
        stderr_path = records / "provider.stderr.txt"
        prompt = self._prompt(diagnoses, parent_version, edit_budget)
        command = [
            self.executable,
            "exec",
            "--ephemeral",
            "--sandbox",
            "workspace-write",
            "--json",
            "--output-schema",
            str(self.schema_path),
            "--output-last-message",
            str(output_path),
            "--cd",
            str(workspace_path),
            prompt,
        ]
        started = datetime.now(timezone.utc)
        status = "failed"
        error: str | None = None
        exit_code: int | None = None
        patch: CandidatePatch | None = None
        try:
            completed = self.runner(command, workspace_path, self.timeout_seconds)
            exit_code = completed.returncode
            stdout_path.write_text(completed.stdout or "", encoding="utf-8", newline="\n")
            stderr_path.write_text(completed.stderr or "", encoding="utf-8", newline="\n")
            if completed.returncode != 0:
                error = f"provider exited with code {completed.returncode}"
            elif not output_path.exists():
                error = "provider did not write structured output"
            else:
                try:
                    payload = json.loads(output_path.read_text(encoding="utf-8"))
                    patch = CandidatePatch.model_validate(payload)
                    status = "completed"
                except (json.JSONDecodeError, ValueError) as exc:
                    error = f"invalid provider JSON: {exc}"
        except subprocess.TimeoutExpired as exc:
            status = "timeout"
            error = f"provider timeout after {exc.timeout} seconds"
            stderr_path.write_text(error, encoding="utf-8", newline="\n")
        except FileNotFoundError as exc:
            status = "unavailable"
            error = str(exc)
            stderr_path.write_text(error, encoding="utf-8", newline="\n")
        ended = datetime.now(timezone.utc)
        output_ref = sha256_file(output_path) if output_path.exists() else None
        record = ProviderRecord(
            provider="codex-cli",
            provider_version=self.provider_version,
            model_identity=patch.model_identity if patch else None,
            command=command[:-1] + ["<prompt:redacted>"],
            prompt_hash=canonical_json_hash({"prompt": prompt}),
            workspace_hash=_workspace_hash(workspace_path),
            started_at=started,
            ended_at=ended,
            exit_code=exit_code,
            status=status,
            output_ref=output_ref,
            error=error,
        )
        (records / "provider_record.json").write_text(
            json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return patch, record

    @staticmethod
    def _prompt(diagnoses: Sequence[FailureDiagnosis], parent_version: str, edit_budget: int) -> str:
        context = [item.model_dump(mode="json") for item in diagnoses]
        return (
            "Return only JSON matching the supplied schema. Propose a bounded candidate patch for "
            "the local Office pilot. You may edit only skill.json. Do not access parent directories, "
            "hidden tasks, evaluators, governance files, credentials, or the source repository. "
            f"Parent version: {parent_version}. Edit budget: {edit_budget}. "
            f"Diagnoses: {json.dumps(context, sort_keys=True)}"
        )


class DeterministicCandidateProvider:
    provider_version = "deterministic-1"

    def generate(
        self,
        workspace: str | Path,
        diagnoses: Sequence[FailureDiagnosis],
        parent_version: str,
        edit_budget: int,
        record_root: str | Path,
    ) -> tuple[CandidatePatch, ProviderRecord]:
        started = datetime.now(timezone.utc)
        diagnosis_refs = [ref for item in diagnoses for ref in item.evidence_refs] or ["0" * 64]
        candidate = CandidatePatch(
            candidate_id=canonical_json_hash({"parent": parent_version, "diagnoses": diagnosis_refs})[:20],
            parent_version=parent_version,
            provider="deterministic",
            provider_version=self.provider_version,
            diagnosis_refs=diagnosis_refs,
            atomic_edits=[
                AtomicEdit(
                    component="prompt",
                    target_path="skill.json",
                    hypothesis="use the required task marker rather than the task identifier",
                    expected_metric="task_success_rate",
                    patch=json.dumps({"marker_source": "required_text"}, sort_keys=True),
                )
            ],
            edit_budget=max(1, edit_budget),
            created_at=started,
        )
        records = Path(record_root)
        records.mkdir(parents=True, exist_ok=True)
        output_path = records / "candidate.json"
        output_path.write_text(json.dumps(candidate.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        ended = datetime.now(timezone.utc)
        record = ProviderRecord(
            provider="deterministic",
            provider_version=self.provider_version,
            command=[],
            prompt_hash=canonical_json_hash({"diagnosis_refs": diagnosis_refs}),
            workspace_hash=_workspace_hash(Path(workspace)),
            started_at=started,
            ended_at=ended,
            exit_code=0,
            status="completed",
            output_ref=sha256_file(output_path),
        )
        (records / "provider_record.json").write_text(json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return candidate, record
