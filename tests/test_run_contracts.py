"""T03 contracts: failure attribution and unknown telemetry stay explicit."""

import pytest
from pydantic import ValidationError

from workagent_rsi.run_contracts import (
    AssessmentOutcome, ExecutionOutcome, ProtocolCapabilities, RunUsage,
    assessment_from_legacy, execution_from_legacy,
)
from workagent_rsi.costs import usage_from_legacy_costs


def test_model_only_approval_can_explicitly_forbid_all_tools():
    from datetime import datetime, timezone
    from workagent_rsi.run_contracts import LiveCallPolicy
    policy=LiveCallPolicy(allow_live_calls=True,approved_by_user=True,provider='codex-cli',model='test',
        max_model_calls=2,max_tool_calls=0,max_wall_seconds=60,
        approved_at=datetime.now(timezone.utc),approval_source='authored zero-tool approval fixture')
    policy.require_authorized(provider='codex-cli',model='test',endpoint=None)
    assert policy.max_tool_calls==0
    with pytest.raises(ValidationError):
        LiveCallPolicy.model_validate({**policy.model_dump(),'max_tool_calls':-1})


def test_absent_usage_is_null_and_zero_requires_an_observation():
    usage = RunUsage()
    assert usage.tokens is None and usage.cost_usd is None
    assert usage.statuses["tokens"] == "unavailable"
    observed = RunUsage(tokens=0, statuses={"tokens": "available"})
    assert observed.tokens == 0 and observed.statuses["tokens"] == "available"
    with pytest.raises(ValidationError):
        RunUsage(tokens=0)
    with pytest.raises(ValidationError):
        RunUsage(tokens=None, statuses={"tokens": "available"})


@pytest.mark.parametrize("bad", [-1, True, "5"])
def test_usage_rejects_negative_boolean_and_coerced_counts(bad):
    with pytest.raises(ValidationError):
        RunUsage(tokens=bad, statuses={"tokens": "available"})


def test_legacy_failure_attribution_and_existing_result_are_preserved():
    result = {"state": "FAILED", "artifacts": [], "failure": {
        "message": "SyntaxError", "failure_origin": "agent_execution",
    }}
    outcome = execution_from_legacy(result)
    assert outcome.status == "failed" and outcome.failure_origin == "agent_execution"
    assert result["failure"]["message"] == "SyntaxError"
    unknown = execution_from_legacy({"state": "FAILED", "failure": {"message": "ambiguous legacy exception"}})
    assert unknown.failure_origin is None
    timeout = execution_from_legacy({"state": "UNAVAILABLE", "failure": {"status": "timeout"}})
    assert timeout.status == "timeout" and timeout.failure_origin == "environment"
    with pytest.raises(ValidationError):
        ExecutionOutcome(status="succeeded", failure_origin="agent_execution")


def test_assessment_adapter_does_not_invent_quality_for_execution_failure():
    failure = assessment_from_legacy({"state": "FAILED", "failure": {"message": "SyntaxError"}})
    assert failure.status == "not_run" and failure.score is None
    gap = assessment_from_legacy({"evaluation": {"passed": False, "score": None,
                                                "channel_status": {"assessment": "incomplete"}}})
    assert gap.status == "incomplete" and gap.failure_origin == "assessment_gap"
    defect = assessment_from_legacy({"evaluation": {"passed": False, "score": .25}})
    assert defect.status == "fail" and defect.score == .25
    assert defect.failure_origin == "artifact_defect"
    with pytest.raises(ValidationError):
        AssessmentOutcome(status="unavailable", score=0, failure_origin="assessment_gap")


def test_protocol_capabilities_do_not_transfer_from_executor_to_judge():
    executor = ProtocolCapabilities(role="executor", chat_completions="available")
    judge = ProtocolCapabilities(role="judge")
    assert executor.responses == "not_probed"
    assert judge.chat_completions == judge.responses == judge.image_input == judge.structured_output == "not_probed"
    with pytest.raises(ValidationError):
        ProtocolCapabilities(role="judge", image_input=True)


def test_cost_compatibility_retains_observed_zero_and_missing_channels():
    old = {"token_count": {"value": None, "status": "unavailable"},
           "tool_calls": {"value": 0, "status": "available"},
           "wall_time_seconds": {"value": 1.5, "status": "available"}}
    usage = usage_from_legacy_costs(old)
    assert usage.tokens is None and usage.cost_usd is None
    assert usage.tool_calls == 0 and usage.statuses["tool_calls"] == "available"
    assert usage.wall_seconds == 1.5
    assert old["token_count"]["value"] is None


def test_unknown_failure_origins_and_nan_quality_are_rejected():
    with pytest.raises(ValidationError):
        ExecutionOutcome(status="failed", failure_origin="guess")
    with pytest.raises(ValidationError):
        AssessmentOutcome(status="pass", score=float("nan"))
