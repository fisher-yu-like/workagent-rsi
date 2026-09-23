from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


RiskLevel = Literal["low", "medium", "high"]


class TaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    domain: str
    instruction: str
    input_files: tuple[str, ...] = ()
    expected_constraints: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = "low"
    hidden_test: bool = False

    @field_validator("task_id", "domain", "instruction")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be empty")
        return value


class SkillManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    version: str
    domain: str
    description: str
    triggers: list[str]
    inputs: list[str]
    outputs: list[str]
    tools: list[str]
    preconditions: list[str]
    postconditions: list[str]
    risk_level: RiskLevel
    dependencies: list[str]
    tests: list[str]
    evaluator_config: dict[str, Any]
    rollback_policy: dict[str, Any]


class ArtifactRef(BaseModel):
    artifact_id: str
    path: str
    sha256: str
    media_type: str
    size_bytes: int


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    ok: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class EvaluationReport(BaseModel):
    passed: bool
    score: float
    critical_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    dimensions: dict[str, float] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)

