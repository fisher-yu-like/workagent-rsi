from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Additive v2 contracts. Existing report schemas and callers are unchanged.
from .run_contracts import AssessmentOutcome, ExecutionOutcome, FailureOrigin, LiveCallPolicy, ProtocolCapabilities, RunUsage


RiskLevel = Literal["low", "medium", "high"]


class TaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    domain: str
    instruction: str
    input_files: tuple[str, ...] = ()
    execution_mode: Literal['create','edit'] | None = None
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
    name: str | None = None
    file_name: str | None = None


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    ok: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class EvaluationReport(BaseModel):
    passed: bool
    score: float | None
    critical_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    dimensions: dict[str, float | None] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    channel_status: dict[str, str] = Field(default_factory=dict)
    assessment_identity: str | None = None
    report_paths: dict[str, str] = Field(default_factory=dict)
    score_semantics: Literal['legacy','task-v2','llm-task-review-v1','smoke'] = 'legacy'
    task_acceptance: Literal['PASS','PARTIAL','FAIL','NEEDS_REVIEW','INCOMPLETE','NOT_ASSESSED'] | None = None
    quality_score: float | None = Field(default=None,ge=0,le=1)
    assessment_outcome: AssessmentOutcome | None = None

    @model_validator(mode='after')
    def versioned_task_semantics(self):
        if self.score_semantics in {'task-v2','llm-task-review-v1'}:
            outcome=self.assessment_outcome
            if outcome is None or self.task_acceptance!=outcome.task_acceptance:
                raise ValueError('versioned evaluation requires the same explicit task outcome')
            if self.passed != (self.task_acceptance=='PASS'):
                raise ValueError('passed must reflect task acceptance')
            if self.score!=self.quality_score or self.quality_score!=outcome.quality_score:
                raise ValueError('versioned quality fields must agree')
        return self

