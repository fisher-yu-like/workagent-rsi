from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Component = Literal["prompt", "tool_policy", "context", "office_script", "verifier_rule", "candidate_test"]
ExperimentStatus = Literal["completed", "failed", "unavailable", "blocked"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AtomicEdit(StrictModel):
    component: Component
    target_path: str
    hypothesis: str = Field(min_length=1)
    expected_metric: str = Field(min_length=1)
    patch: str = Field(min_length=1)

    @field_validator("target_path")
    @classmethod
    def relative_safe_path(cls, value: str) -> str:
        if "\\" in value or ":" in value:
            raise ValueError("target_path must use a relative POSIX path")
        path = PurePosixPath(value)
        if path.is_absolute() or not value or ".." in path.parts or "." == value:
            raise ValueError("target_path must remain inside candidate workspace")
        return value


class CandidatePatch(StrictModel):
    candidate_id: str = Field(min_length=1)
    parent_version: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    model_identity: str | None = None
    diagnosis_refs: list[str] = Field(min_length=1)
    atomic_edits: list[AtomicEdit] = Field(min_length=1)
    new_tests: list[str] = Field(default_factory=list)
    edit_budget: int = Field(ge=1)
    created_at: datetime


class FailureDiagnosis(StrictModel):
    diagnosis_id: str
    run_ids: list[str] = Field(min_length=1)
    failure_class: Literal["input", "planning", "tool", "format", "semantic", "visual", "evaluator", "safety"]
    evidence_refs: list[str] = Field(min_length=1)
    causal_hypothesis: str = Field(min_length=1)
    recommended_component: Component
    confidence: float = Field(ge=0.0, le=1.0)


class VerificationReport(StrictModel):
    candidate_id: str
    passed: bool
    critical_violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    executed_checks: list[str] = Field(min_length=1)
    test_results: dict[str, Any] = Field(default_factory=dict)
    artifact_results: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(min_length=1)


class SkillVersion(StrictModel):
    skill_id: str
    version: str
    parent_version: str | None = None
    content_hash: str
    manifest_hash: str
    candidate_id: str | None = None
    status: Literal["champion", "accepted", "rejected", "rolled_back"]
    evidence_refs: list[str] = Field(min_length=1)
    created_at: datetime


class PromotionDecision(StrictModel):
    candidate_id: str
    decision: Literal["accept", "reject", "human_review"]
    gate_results: dict[str, bool]
    develop_delta: float | None = None
    regression_delta: float | None = None
    hidden_delta: float | None = None
    ood_delta: float | None = None
    cost_delta: float | None = None
    evidence_refs: list[str] = Field(min_length=1)


class EvaluationContract(StrictModel):
    contract_id: str
    dataset_hash: str
    split_hashes: dict[str, str]
    evaluator_hash: str
    provider_policy: str
    seeds: list[int] = Field(min_length=1)
    repeats: int = Field(ge=1)
    timeout_seconds: int = Field(ge=1)
    thresholds: dict[str, float]
    git_commit: str


class ProviderRecord(StrictModel):
    provider: str
    provider_version: str
    model_identity: str | None = None
    command: list[str]
    prompt_hash: str
    workspace_hash: str
    started_at: datetime
    ended_at: datetime
    exit_code: int | None = None
    status: Literal["completed", "failed", "unavailable", "timeout"]
    output_ref: str | None = None
    error: str | None = None


class ExperimentResult(StrictModel):
    experiment_id: str
    invocation_id: str
    status: ExperimentStatus
    contract_hash: str
    metrics: dict[str, float] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(min_length=1)
    failure: str | None = None
