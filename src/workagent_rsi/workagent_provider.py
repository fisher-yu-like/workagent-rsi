"""Typed contracts for the local Office WorkAgent provider."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .hashing import canonical_json_hash, sha256_file
from .rsi_contracts import ProviderRecord


_RELATIVE_POSIX_PATH_PATTERN = r"^(?!/)(?!.*[:\\])(?!.*(?:^|/)\.{1,2}(?:/|$))[^/]+(?:/[^/]+)*$"


class WorkAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = "qwen2.5:7b"
    executable: str = "codex"
    timeout_seconds: int = Field(default=600, ge=1)
    max_output_files: int = Field(default=8, ge=1)
    max_artifact_bytes: int = Field(default=104857600, ge=1)
    verify_com: bool = True


class WorkAgentSkill(BaseModel):
    """The only candidate-controlled part of a WorkAgent Office run."""

    model_config = ConfigDict(extra="forbid")
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    instructions: str = Field(min_length=1, max_length=20000)


class AgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "failed"]
    deliverables: list[str] = Field(json_schema_extra={"items": {"type": "string", "pattern": _RELATIVE_POSIX_PATH_PATTERN}})
    summary: str
    input_files_used: list[str] = Field(json_schema_extra={"items": {"type": "string", "pattern": _RELATIVE_POSIX_PATH_PATTERN}})

    @field_validator("deliverables", "input_files_used")
    @classmethod
    def relative_posix_paths(cls, values: list[str]) -> list[str]:
        for value in values:
            if (
                not value
                or value.startswith("/")
                or "\\" in value
                or ":" in value
                or any(part in ("", ".", "..") for part in value.split("/"))
            ):
                raise ValueError("response paths must be relative POSIX paths without empty or traversal components")
        return values


class ProviderOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "failed", "unavailable", "timeout"]
    response: AgentResponse | None = None
    record: ProviderRecord | None = None
    error: str | None = None


def build_agent_response_schema() -> dict[str, object]:
    """Return the structured-output schema supplied to the Codex CLI."""
    return AgentResponse.model_json_schema()


class CodexOfficeProvider:
    def __init__(self, config: WorkAgentConfig) -> None:
        self.config = config
        self.schema_path = (Path(__file__).parent / "schemas" / "agent_response.schema.json").resolve()

    def command(self, workspace: Path, response_path: Path, schema_path: Path) -> list[str]:
        return [
            self.config.executable,
            "exec",
            "--ignore-user-config",
            "--oss",
            "--local-provider",
            "ollama",
            "--model",
            self.config.model,
            "--ephemeral",
            "--sandbox",
            "workspace-write",
            "--json",
            "--output-schema",
            str(schema_path.resolve()),
            "--output-last-message",
            str(response_path.resolve()),
            "--cd",
            str(workspace.resolve()),
            "-",
        ]

    def run(self, prompt: str, workspace: Path, record_root: Path) -> ProviderOutcome:
        workspace = Path(workspace).resolve()
        records = Path(record_root).resolve()
        workspace_hash = canonical_json_hash({
            path.relative_to(workspace).as_posix(): sha256_file(path)
            for path in sorted(workspace.rglob("*"))
            if path.is_file() and ".git" not in path.parts and "provider_records" not in path.parts
        })
        records.mkdir(parents=True, exist_ok=True)
        response_path = workspace / f"agent_response-{uuid4().hex}.json"
        canonical_response_path = workspace / "agent_response.json"
        canonical_response_path.unlink(missing_ok=True)
        command = self.command(workspace, response_path, self.schema_path)
        (records / "prompt.md").write_text(prompt, encoding="utf-8", newline="\n")
        (records / "command.json").write_text(json.dumps(command, indent=2) + "\n", encoding="utf-8", newline="\n")

        started = datetime.now(timezone.utc)
        status = "failed"
        response = None
        error = None
        exit_code = None
        stdout = ""
        stderr = ""
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                input=prompt,
                timeout=self.config.timeout_seconds,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            exit_code = completed.returncode
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            if exit_code != 0:
                error = f"provider exited with code {exit_code}"
            elif not response_path.exists():
                error = "provider did not write structured output"
            else:
                try:
                    response = AgentResponse.model_validate_json(response_path.read_text(encoding="utf-8"))
                    status = response.status
                    shutil.copyfile(response_path, canonical_response_path)
                    shutil.copyfile(response_path, records / "agent_response.json")
                except ValueError as exc:
                    error = f"invalid provider response: {exc}"
        except subprocess.TimeoutExpired as exc:
            status = "timeout"
            error = f"provider timeout after {exc.timeout} seconds"
            stdout = _decode_process_output(exc.stdout)
            stderr = _decode_process_output(exc.stderr)
        except OSError as exc:
            status = "unavailable"
            error = str(exc)

        (records / "provider.stdout.jsonl").write_text(stdout, encoding="utf-8", newline="\n")
        (records / "provider.stderr.txt").write_text(stderr, encoding="utf-8", newline="\n")
        ended = datetime.now(timezone.utc)
        record = ProviderRecord(
            provider="codex-cli",
            provider_version="local-1",
            model_identity=f"ollama:{self.config.model}",
            command=command,
            prompt_hash=canonical_json_hash({"prompt": prompt}),
            workspace_hash=workspace_hash,
            started_at=started,
            ended_at=ended,
            exit_code=exit_code,
            status=status,
            output_ref=sha256_file(response_path) if response is not None else None,
            error=error,
        )
        (records / "provider_record.json").write_text(
            json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return ProviderOutcome(status=status, response=response, record=record, error=error)


def _decode_process_output(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""
