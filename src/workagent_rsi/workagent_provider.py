"""Typed contracts for the local Office WorkAgent provider."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
