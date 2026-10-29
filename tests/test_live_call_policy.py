"""T03 section 2.7: authorization is explicit and budgets never default open."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from workagent_rsi.run_contracts import LiveCallPolicy


def approved(**changes):
    return dict(allow_live_calls=True, approved_by_user=True,
                provider="openai-chat", model="offline-test-model", endpoint="https://api.example.test/v1",
                max_model_calls=3, max_tool_calls=8, max_wall_seconds=60,
                approved_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
                approval_source="user: explicit call/time limits accepted", **changes)


def test_default_policy_is_disabled_and_roundtrips_without_credentials():
    policy = LiveCallPolicy()
    assert policy.allow_live_calls is policy.approved_by_user is False
    assert policy.max_model_calls is policy.max_cost_usd is None
    with pytest.raises(ValueError, match="disabled"):
        policy.require_authorized(provider="openai-chat", model="offline-test-model", endpoint="https://api.example.test/v1")
    assert LiveCallPolicy.model_validate_json(policy.model_dump_json()) == policy


def test_enabled_policy_requires_approval_identity_and_hard_caps():
    for field in ("approved_by_user", "provider", "model", "endpoint", "max_model_calls", "max_tool_calls",
                  "max_wall_seconds", "approved_at", "approval_source"):
        values = approved()
        values.pop(field)
        with pytest.raises(ValidationError):
            LiveCallPolicy(**values)


def test_call_time_caps_can_replace_unobservable_cost_and_identity_must_match():
    policy = LiveCallPolicy(**approved())
    assert policy.max_cost_usd is None
    policy.require_authorized(provider="openai-chat", model="offline-test-model", endpoint="https://api.example.test/v1")
    for changes in ({"model": "other-model"}, {"provider": "candidate"}, {"endpoint": "https://elsewhere.test/v1"}):
        identity = dict(provider="openai-chat", model="offline-test-model", endpoint="https://api.example.test/v1")
        identity.update(changes)
        with pytest.raises(ValueError, match="identity"):
            policy.require_authorized(**identity)


@pytest.mark.parametrize("endpoint", ["https://user:password@example.test", "https://example.test?api_key=dummy",
                                      "https://example.test/#dummy", "file:///tmp/api", "https://example.test/token/dummy"])
def test_credential_bearing_or_non_http_endpoints_are_rejected(endpoint):
    with pytest.raises(ValidationError):
        LiveCallPolicy(endpoint=endpoint)


@pytest.mark.parametrize("changes", [{"max_model_calls": 0}, {"max_tool_calls": True}, {"max_wall_seconds": "60"},
                                     {"max_cost_usd": float("inf")}, {"api_key": "dummy"},
                                     {"approved_at": datetime(2026, 10, 23)}, {"model": " "}])
def test_policy_rejects_ambiguous_metadata_and_invalid_limits(changes):
    values = approved()
    values.update(changes)
    with pytest.raises(ValidationError):
        LiveCallPolicy(**values)


def test_cli_policy_can_explicitly_use_no_endpoint():
    values = approved()
    values.update(provider="codex-cli", endpoint=None)
    policy = LiveCallPolicy(**values)
    policy.require_authorized(provider="codex-cli", model="offline-test-model", endpoint=None)
