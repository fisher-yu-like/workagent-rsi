from workagent_rsi.contracts import TaskSpec, SkillManifest


def test_task_spec_rejects_unknown_risk_level():
    try:
        TaskSpec(
            task_id="t1",
            domain="smoke",
            instruction="echo",
            risk_level="unknown",
        )
    except ValueError as exc:
        assert "risk_level" in str(exc)
    else:
        raise AssertionError("invalid risk level must be rejected")


def test_skill_manifest_requires_versioned_contract_fields():
    manifest = SkillManifest(
        id="smoke.echo",
        version="0.1.0",
        domain="smoke",
        description="deterministic smoke skill",
        triggers=["smoke"],
        inputs=["instruction"],
        outputs=["artifact"],
        tools=[],
        preconditions=[],
        postconditions=["artifact_exists"],
        risk_level="low",
        dependencies=[],
        tests=["smoke_echo"],
        evaluator_config={"required_text": "hello"},
        rollback_policy={"on_regression": "restore_parent"},
    )
    assert manifest.version == "0.1.0"

