from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from .run_contracts import FailureOrigin


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
    edit_budget: int = Field(ge=1, strict=True)
    created_at: datetime


class CandidateNormalizationRecord(StrictModel):
    schema_version: Literal['candidate-normalization-v1'] = 'candidate-normalization-v1'
    status: Literal['accepted', 'rejected']
    context_hash: str
    raw_sha256: str | None = None
    response_bytes_sha256: str | None = None
    raw_hash_kind: Literal['canonical_json', 'raw_bytes'] = 'canonical_json'
    normalized_sha256: str | None = None
    envelope: str | None = None
    mappings: list[dict[str, str]] = Field(default_factory=list)
    metadata_provenance: dict[str, str] = Field(default_factory=dict)
    error: str | None = None


class DiagnosisEvidence(StrictModel):
    ref: str
    kind: Literal['script','stderr','input_manifest','file_events']
    quote: str
    source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)


class FailureDiagnosis(StrictModel):
    diagnosis_id: str
    run_ids: list[str] = Field(min_length=1)
    failure_class: Literal["input", "planning", "tool", "format", "semantic", "visual", "evaluator", "safety"]
    evidence_refs: list[str] = Field(min_length=1)
    causal_hypothesis: str = Field(min_length=1)
    recommended_component: Component
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_basis: str = 'uncalibrated_legacy_rule_strength'
    recommended_action: str | None = None
    falsification_check: str | None = None
    evidence_details: list[DiagnosisEvidence] = Field(default_factory=list)
    feedback_visibility: Literal['develop','evaluation_only'] = 'develop'


class VerificationReport(StrictModel):
    candidate_id: str
    passed: bool
    critical_violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    executed_checks: list[str] = Field(min_length=1)
    test_results: dict[str, Any] = Field(default_factory=dict)
    artifact_results: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(min_length=1)
    schema_status: Literal['passed', 'failed', 'not_run'] = 'not_run'
    safety_status: Literal['passed', 'failed', 'not_run'] = 'not_run'
    behavior_status: Literal['passed', 'failed', 'not_run', 'unavailable', 'error'] = 'not_run'
    compile_status: Literal['passed', 'failed', 'not_run', 'not_applicable'] = 'not_run'
    quality_verified: bool = False
    behavior_required: bool = False


class BehaviorProbeResult(StrictModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    status: Literal['passed', 'failed', 'not_run', 'unavailable', 'error']
    evidence_kind: Literal['unverified', 'unit_fixture', 'isolated_run'] = 'unverified'
    backend: Literal['docker', 'apptainer-ssh'] | None = None
    taskset_hash: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    parent_package_hash: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    candidate_package_hash: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    isolation_verified: bool = False
    independent_tasks_verified: bool = False
    cleanup_confirmed: bool = False
    protected_regressions: int = Field(default=0, ge=0)
    failed_checks: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


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
    assessment_mode: Literal["legacy", "artifact-v1"] = "legacy"
    assessment_identity: str | None = None
    acceptance_hashes: dict[str, str] = Field(default_factory=dict)
    comparison_policy: dict[str, Any] | None = None
    task_families: dict[str, str] = Field(default_factory=dict)


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
    failure_origin: FailureOrigin | None = None
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
