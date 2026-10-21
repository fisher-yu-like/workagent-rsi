"""Versioned outcomes shared by later hardening modules.

Legacy reports remain unchanged; adapters return new records. Scores use the
legacy Harness scale [0, 1]. These contracts do not wire in repair or change
existing evaluator decisions.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


FailureOrigin = Literal["environment", "agent_execution", "artifact_defect", "assessment_gap", "spec_gap"]
CapabilityStatus = Literal["not_probed", "available", "unavailable", "not_supported"]
USAGE_FIELDS = ("tokens", "tool_calls", "steps", "wall_seconds", "cost_usd")


class RunContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class RunUsage(RunContract):
    tokens: int | None = Field(default=None, ge=0)
    tool_calls: int | None = Field(default=None, ge=0)
    steps: int | None = Field(default=None, ge=0)
    wall_seconds: float | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    statuses: dict[str, Literal["available", "unavailable"]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def observations_match_status(self):
        if set(self.statuses) - set(USAGE_FIELDS):
            raise ValueError("unknown usage channel")
        statuses = {name: self.statuses.get(name, "unavailable") for name in USAGE_FIELDS}
        for name in USAGE_FIELDS:
            if (getattr(self, name) is not None) != (statuses[name] == "available"):
                raise ValueError(f"{name}: numeric usage requires explicit available observation")
        object.__setattr__(self, "statuses", statuses)
        return self


class ProtocolCapabilities(RunContract):
    role: Literal["executor", "candidate", "judge"]
    chat_completions: CapabilityStatus = "not_probed"
    responses: CapabilityStatus = "not_probed"
    image_input: CapabilityStatus = "not_probed"
    structured_output: CapabilityStatus = "not_probed"


class ExecutionOutcome(RunContract):
    schema_version: Literal["run-outcome-v2"] = "run-outcome-v2"
    status: Literal["succeeded", "failed", "unavailable", "timeout", "not_run"]
    failure_origin: FailureOrigin | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    trace_refs: list[str] = Field(default_factory=list)
    usage: RunUsage = Field(default_factory=RunUsage)

    @model_validator(mode="after")
    def failure_has_origin(self):
        if self.status == "succeeded" and self.failure_origin is not None:
            raise ValueError("successful execution cannot carry a failure origin")
        if self.status in {"unavailable", "timeout"} and self.failure_origin is None:
            raise ValueError("unavailable execution requires a failure origin")
        return self


class AssessmentCoverage(RunContract):
    check_completion: float | None = Field(default=None, ge=0, le=1)
    task_requirement_coverage: float | None = Field(default=None, ge=0, le=1)
    evidence_scope: list[str] = Field(default_factory=list)


class AssessmentOutcome(RunContract):
    schema_version: Literal["assessment-outcome-v2"] = "assessment-outcome-v2"
    status: Literal["pass", "partial", "fail", "incomplete", "spec_incomplete", "unavailable", "not_run"]
    failure_origin: FailureOrigin | None = None
    score: float | None = Field(default=None, ge=0, le=1)
    coverage: AssessmentCoverage = Field(default_factory=AssessmentCoverage)
    report_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unknown_quality_remains_null(self):
        if self.status in {"incomplete", "spec_incomplete", "unavailable", "not_run"} and self.score is not None:
            raise ValueError("unobserved quality cannot carry a numeric score")
        if self.status in {"pass", "partial"} and self.score is None:
            raise ValueError("completed quality needs an observed score")
        if self.status == "pass" and self.failure_origin is not None:
            raise ValueError("passed assessment cannot carry a failure origin")
        return self


def execution_from_legacy(result: dict) -> ExecutionOutcome:
    """Adapt recorded state, without guessing causes from exception prose."""
    evaluation = result.get("evaluation")
    failure = result.get("failure") or {}
    state = result.get("state")
    refs = [item.get("artifact_id") or item.get("path") for item in result.get("artifacts", [])]
    refs = [value for value in refs if isinstance(value, str)]
    if evaluation and not failure:
        # Legacy FAILED can mean a completed execution with a defective artifact.
        return ExecutionOutcome(status="succeeded", artifact_refs=refs)
    if state == "SUCCEEDED":
        return ExecutionOutcome(status="succeeded", artifact_refs=refs)
    if state == "UNAVAILABLE" or failure.get("status") in {"timeout", "unavailable"}:
        status = "timeout" if failure.get("status") == "timeout" else "unavailable"
        return ExecutionOutcome(status=status, failure_origin="environment", artifact_refs=refs)
    if state == "FAILED":
        # Generic legacy exceptions do not identify whether execution or a
        # checker failed. Retain null rather than infer a cause from prose.
        origin = failure.get("failure_origin") or failure.get("origin")
        return ExecutionOutcome(status="failed", failure_origin=origin, artifact_refs=refs)
    return ExecutionOutcome(status="not_run", artifact_refs=refs)


def assessment_from_legacy(result: dict) -> AssessmentOutcome:
    evaluation = result.get("evaluation")
    if not evaluation:
        return AssessmentOutcome(status="not_run")
    refs = list((evaluation.get("report_paths") or {}).values())
    score = evaluation.get("score")
    if score is None or evaluation.get("channel_status", {}).get("assessment") == "incomplete":
        return AssessmentOutcome(status="incomplete", failure_origin="assessment_gap", report_refs=refs)
    passed = evaluation.get("passed") is True
    return AssessmentOutcome(status="pass" if passed else "fail", score=score,
                             failure_origin=None if passed else "artifact_defect", report_refs=refs)
