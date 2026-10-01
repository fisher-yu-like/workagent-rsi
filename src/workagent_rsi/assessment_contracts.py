"""Versioned contracts shared by the two fixed artifact assessment skills."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .hashing import canonical_json_hash


CheckStatus = Literal["PASS", "PARTIAL", "FAIL", "NOT_APPLICABLE", "UNAVAILABLE", "ERROR", "NEEDS_REVIEW"]
Visibility = Literal["develop", "evaluation_only"]


class AssessmentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Location(AssessmentModel):
    artifact: str = Field(min_length=1)
    sheet: str | None = None
    cell: str | None = None
    paragraph: int | None = Field(default=None, ge=1)
    heading: str | None = None
    table: int | None = Field(default=None, ge=1)
    row: int | None = Field(default=None, ge=1)
    column: int | None = Field(default=None, ge=1)
    slide: int | None = Field(default=None, ge=1)
    object_id: int | None = Field(default=None, ge=0)
    region: str | None = None


class Requirement(AssessmentModel):
    requirement_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    check: str = Field(min_length=1)
    location: Location
    expected: Any = None
    options: dict[str, Any] = Field(default_factory=dict)
    critical: bool = False
    dimension: str = Field(min_length=1)
    weight: float = Field(default=1, ge=0)
    tolerance: float = Field(default=0, ge=0)
    applicable: bool = True
    applicability_reason: str = Field(default="declared by task specification", min_length=1)
    evidence_source: str = Field(min_length=1)
    feedback_visibility: Visibility = "develop"
    repair_hint: str = "Recreate the affected artifact to meet this requirement."
    skill_improvement_hint: str | None = None
    # Semantic issue identity: several observations must not deduct for the same issue.
    scoring_key: str | None = None


class AcceptanceSpec(AssessmentModel):
    schema_version: Literal["artifact-assessment-v1"] = "artifact-assessment-v1"
    task_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    artifacts: dict[str, Literal["excel", "word", "powerpoint"]]
    requirements: list[Requirement] = Field(min_length=1)
    dimension_weights: dict[str, float]
    quality_threshold: float = Field(default=80, ge=0, le=100)
    input_hashes: dict[str, str] = Field(default_factory=dict)
    scope_note: str = "Only the declared requirements are assessed."

    @model_validator(mode="after")
    def consistent(self):
        ids = [r.requirement_id for r in self.requirements]
        keys = [r.scoring_key or r.requirement_id for r in self.requirements if r.weight > 0]
        if len(set(ids)) != len(ids) or len(set(keys)) != len(keys):
            raise ValueError("duplicate requirement or scoring key")
        if not self.artifacts:
            raise ValueError("at least one artifact is required")
        if not self.dimension_weights or any(not 0 < w <= 1 for w in self.dimension_weights.values()):
            raise ValueError("dimension weights must be finite and positive")
        if abs(sum(self.dimension_weights.values()) - 1) > 1e-8:
            raise ValueError("dimension weights must sum to one")
        for r in self.requirements:
            if r.location.artifact not in self.artifacts or r.dimension not in self.dimension_weights:
                raise ValueError("unknown artifact or dimension")
        for dimension in self.dimension_weights:
            if not any(r.dimension == dimension and r.applicable and r.weight > 0 for r in self.requirements):
                raise ValueError("each weighted dimension needs an applicable scoring requirement")
        return self

    def fingerprint(self) -> str:
        return canonical_json_hash(self.model_dump(mode="json"))


class Evidence(AssessmentModel):
    evidence_id: str
    requirement_id: str
    location: Location
    source: str
    observed: Any = None
    artifact_sha256: str | None = None
    artifact_hashes: dict[str, str | None] = Field(default_factory=dict)


class CheckRecord(AssessmentModel):
    requirement_id: str
    status: CheckStatus
    completion: float | None = Field(default=None, ge=0, le=1)
    location: Location
    observed: Any = None
    expected: Any = None
    evidence_refs: list[str] = Field(min_length=1)
    message: str = ""

    @model_validator(mode="after")
    def status_matches_completion(self):
        known = self.status in {"PASS", "PARTIAL", "FAIL"}
        if known != (self.completion is not None):
            raise ValueError("only completed checks may carry a numeric completion")
        if self.status == "PASS" and self.completion != 1:
            raise ValueError("PASS requires completion=1")
        if self.status == "FAIL" and self.completion != 0:
            raise ValueError("FAIL requires completion=0")
        if self.status == "PARTIAL" and not 0 < self.completion < 1:
            raise ValueError("PARTIAL requires 0 < completion < 1")
        return self


class Assessment(AssessmentModel):
    spec: AcceptanceSpec
    spec_hash: str
    evaluator_identity: str
    artifact_hashes: dict[str, str | None]
    checks: list[CheckRecord]
    evidence: list[Evidence]
    telemetry: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bound_to_spec(self):
        if self.spec_hash != self.spec.fingerprint():
            raise ValueError("assessment spec identity mismatch")
        expected = {r.requirement_id: r for r in self.spec.requirements}
        if len(self.checks) != len(expected) or {c.requirement_id for c in self.checks} != set(expected):
            raise ValueError("exactly one check is required for every requirement")
        evidence = {e.evidence_id: e for e in self.evidence}
        if len(evidence) != len(self.evidence):
            raise ValueError("duplicate evidence id")
        for c in self.checks:
            r = expected[c.requirement_id]
            if (c.status == "NOT_APPLICABLE") != (not r.applicable):
                raise ValueError("applicability must be fixed before assessment")
            if c.expected != r.expected:
                raise ValueError("check changed the expected value")
            if any(ref not in evidence or evidence[ref].requirement_id != c.requirement_id for ref in c.evidence_refs):
                raise ValueError("evidence must refer to this requirement")
        return self


class Coverage(AssessmentModel):
    applicable: int = Field(ge=0)
    completed: int = Field(ge=0)
    ratio: float = Field(ge=0, le=1)
    status_counts: dict[str, int]


class ScoreReport(AssessmentModel):
    task_id: str
    spec_hash: str
    evaluator_identity: str
    artifact_hashes: dict[str, str | None]
    acceptance_status: Literal["PASS", "FAIL", "INCOMPLETE"]
    total_score: float | None = Field(default=None, ge=0, le=100)
    dimension_scores: dict[str, float | None]
    coverage: Coverage
    criterion_results: list[CheckRecord]
    evidence_refs: list[str]
    scope_note: str


class ArtifactIssue(AssessmentModel):
    issue_id: str
    requirement_id: str
    kind: Literal["artifact_defect", "assessment_gap"]
    location: Location
    observed: Any = None
    expected: Any = None
    evidence_refs: list[str]
    severity: Literal["blocking", "major", "minor", "advisory"]
    cause_hypothesis: str | None = None
    repair_hint: str
    skill_improvement_hint: str | None = None
    recheck_ids: list[str]
    feedback_visibility: Visibility


class IssueReport(AssessmentModel):
    task_id: str
    spec_hash: str
    evaluator_identity: str
    artifact_hashes: dict[str, str | None]
    issues: list[ArtifactIssue]


class RSIFeedback(AssessmentModel):
    schema_version: Literal["artifact-feedback-v1"] = "artifact-feedback-v1"
    split: Literal["develop"] = "develop"
    mode: Literal["score_only", "brief", "structured"] = "structured"
    tasks: list[dict[str, Any]]
    issue_groups: dict[str, list[str]] = Field(default_factory=dict)
