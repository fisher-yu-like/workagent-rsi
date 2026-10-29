"""Versioned contracts shared by the two fixed artifact assessment skills."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .hashing import canonical_json_hash


CheckStatus = Literal["PASS", "PARTIAL", "FAIL", "NOT_APPLICABLE", "UNAVAILABLE", "ERROR", "NEEDS_REVIEW"]
Visibility = Literal["develop", "evaluation_only"]


class AssessmentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Location(AssessmentModel):
    artifact: str = Field(min_length=1)
    sheet: str | None = None
    cell: str | None = None
    paragraph: int | None = Field(default=None, ge=1, strict=True)
    heading: str | None = None
    table: int | None = Field(default=None, ge=1, strict=True)
    row: int | None = Field(default=None, ge=1, strict=True)
    column: int | None = Field(default=None, ge=1, strict=True)
    slide: int | None = Field(default=None, ge=1, strict=True)
    object_id: int | None = Field(default=None, ge=0, strict=True)
    region: str | None = None
    group_path: list[int] | None = None

    @field_validator('group_path',mode='before')
    @classmethod
    def explicit_group_ids(cls,value):
        if value is not None and (not isinstance(value,list) or not value or any(type(v) is not int or v<1 for v in value)):
            raise ValueError('group_path requires a nonempty list of positive integer group IDs')
        return value


class Requirement(AssessmentModel):
    requirement_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    check: str = Field(min_length=1)
    location: Location
    expected: Any = None
    options: dict[str, Any] = Field(default_factory=dict)
    critical: bool = Field(default=False, strict=True)
    dimension: str = Field(min_length=1)
    weight: float = Field(default=1, ge=0, strict=True)
    tolerance: float = Field(default=0, ge=0, strict=True)
    applicable: bool = Field(default=True, strict=True)
    applicability_reason: str = Field(default="declared by task specification", min_length=1)
    evidence_source: str = Field(min_length=1)
    feedback_visibility: Visibility = "develop"
    repair_hint: str = "Recreate the affected artifact to meet this requirement."
    skill_improvement_hint: str | None = None
    # Semantic issue identity: several observations must not deduct for the same issue.
    scoring_key: str | None = None


EvaluationProfile = Literal['structural_only', 'task_acceptance', 'research']


class TaskRequirement(AssessmentModel):
    requirement_id: str = Field(min_length=1)
    source_quote: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    obligation: str = Field(min_length=1)
    mandatory: bool = Field(default=True, strict=True)
    validation_method: Literal['deterministic', 'semantic', 'visual', 'human', 'uncovered']
    check_ids: list[str] = Field(default_factory=list)


class RequirementInventory(AssessmentModel):
    task_id: str = Field(min_length=1)
    requirements: list[TaskRequirement]
    reviewed: bool = Field(default=False, strict=True)
    provenance: dict[str, Any] = Field(default_factory=dict)


class RequirementCoverage(AssessmentModel):
    mandatory: int = Field(ge=0)
    covered: int = Field(ge=0)
    ratio: float = Field(ge=0, le=1)


class SpecAdmissionReport(AssessmentModel):
    status: Literal['PASS', 'SPEC_INCOMPLETE', 'ASSESSMENT_INCOMPLETE', 'NOT_ASSESSED', 'LEGACY_UNREVIEWED']
    evaluation_profile: EvaluationProfile | None = None
    requirement_coverage: RequirementCoverage
    uncovered_requirement_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    mappings: dict[str, list[str]] = Field(default_factory=dict)
    task_hash: str | None = None
    spec_binding_hash: str | None = None
    findings: list['SpecFinding'] = Field(default_factory=list)


class SpecFinding(AssessmentModel):
    requirement_id: str
    origin: Literal['spec_gap', 'assessment_gap']
    message: str


class LegacyAdapterRecord(AssessmentModel):
    key: str
    status: Literal['converted', 'unsupported', 'alias']
    check_ids: list[str] = Field(default_factory=list)
    reason: str


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
    # None is explicit v1 compatibility: declared-check scores only, never
    # evidence of reviewed whole-task coverage. New profiles use admission.
    evaluation_profile: EvaluationProfile | None = None
    task_context: dict[str, Any] | None = None
    requirement_inventory: RequirementInventory | None = None
    legacy_adapter_records: list[LegacyAdapterRecord] = Field(default_factory=list)

    @field_validator('dimension_weights', mode='before')
    @classmethod
    def numeric_dimension_weights(cls, value):
        if isinstance(value,dict) and any(type(w) not in {int,float} for w in value.values()):
            raise ValueError('dimension weights must be numeric, never bool or text')
        return value

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
    requested_location: Location | None = None
    observed_locations: list[Location] = Field(default_factory=list)


class CheckRecord(AssessmentModel):
    requirement_id: str
    status: CheckStatus
    completion: float | None = Field(default=None, ge=0, le=1)
    location: Location
    observed: Any = None
    expected: Any = None
    evidence_refs: list[str] = Field(min_length=1)
    message: str = ""
    failure_origin: Literal['artifact_defect', 'spec_gap', 'assessment_gap'] | None = None
    requested_location: Location | None = None
    observed_locations: list[Location] = Field(default_factory=list)

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
    spec_admission: SpecAdmissionReport | None = None

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
            if c.requested_location is not None and (c.requested_location!=r.location or c.location!=r.location):
                raise ValueError('check changed the requested location')
            if (c.status == "NOT_APPLICABLE") != (not r.applicable):
                raise ValueError("applicability must be fixed before assessment")
            if c.expected != r.expected:
                raise ValueError("check changed the expected value")
            if any(ref not in evidence or evidence[ref].requirement_id != c.requirement_id for ref in c.evidence_refs):
                raise ValueError("evidence must refer to this requirement")
            for ref in c.evidence_refs:
                item=evidence[ref]
                if item.requested_location is not None and item.requested_location!=r.location:
                    raise ValueError('evidence changed the requested location')
                if any(loc.artifact not in self.spec.artifacts for loc in item.observed_locations+c.observed_locations):
                    raise ValueError('observed location references an undeclared artifact')
        return self


class Coverage(AssessmentModel):
    applicable: int = Field(ge=0)
    completed: int = Field(ge=0)
    ratio: float = Field(ge=0, le=1)
    status_counts: dict[str, int]


class ScoreReport(AssessmentModel):
    score_semantics: Literal['declared-check-v1','task-assessment-v2','llm-task-review-v1'] = 'declared-check-v1'
    task_id: str
    spec_hash: str
    evaluator_identity: str
    artifact_hashes: dict[str, str | None]
    acceptance_status: Literal["PASS", "PARTIAL", "FAIL", "NEEDS_REVIEW", "INCOMPLETE"]
    total_score: float | None = Field(default=None, ge=0, le=100)
    dimension_scores: dict[str, float | None]
    coverage: Coverage
    criterion_results: list[CheckRecord]
    evidence_refs: list[str]
    scope_note: str
    spec_admission: SpecAdmissionReport | None = None
    requirement_coverage: RequirementCoverage | None = None
    task_score: float | None = Field(default=None, ge=0, le=100)
    task_acceptance: Literal['PASS', 'PARTIAL', 'FAIL', 'NEEDS_REVIEW', 'INCOMPLETE', 'NOT_ASSESSED'] = 'NOT_ASSESSED'
    check_score: float | None = Field(default=None, ge=0, le=100)
    quality_score: float | None = Field(default=None, ge=0, le=100)


class RepairAction(AssessmentModel):
    target: Literal['artifact','assessment_capability','acceptance_spec']
    description: str = Field(min_length=1)
    locations: list[Location] = Field(default_factory=list)
    evidence_refs: list[str] = Field(min_length=1)

    @model_validator(mode='after')
    def action_scope(self):
        if (self.target=='artifact') != bool(self.locations):
            raise ValueError('only artifact repair actions name artifact edit locations')
        return self


class ArtifactIssue(AssessmentModel):
    issue_id: str
    requirement_id: str
    kind: Literal["artifact_defect", "assessment_gap", "spec_gap"]
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
    requested_location: Location | None = None
    observed_locations: list[Location] = Field(default_factory=list)
    failure_origin: Literal['artifact_defect','spec_gap','assessment_gap'] | None = None
    affected_requirements: list[str] = Field(default_factory=list)
    repair_action: RepairAction | None = None
    verification_steps: list[str] = Field(default_factory=list)
    impact: str | None = None
    qualification_only: bool = Field(default=False,strict=True)

    @model_validator(mode='after')
    def actionable_issue(self):
        if self.repair_action is not None:
            target={'artifact_defect':'artifact','assessment_gap':'assessment_capability','spec_gap':'acceptance_spec'}[self.kind]
            if self.failure_origin!=self.kind or self.repair_action.target!=target:
                raise ValueError('repair action must target the observed failure origin')
            if not self.affected_requirements or not self.verification_steps:
                raise ValueError('actionable issue requires affected requirements and verification steps')
            if self.repair_action.evidence_refs!=self.evidence_refs:
                raise ValueError('repair action must cite the same frozen evidence as the issue')
        return self


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
