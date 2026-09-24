from datetime import datetime, timezone

from workagent_rsi.leakage import LeakageCritic
from workagent_rsi.rsi_contracts import AtomicEdit, CandidatePatch


def candidate(target="skill.json", patch='{"marker_source":"required_text"}') -> CandidatePatch:
    return CandidatePatch(
        candidate_id="c1",
        parent_version="0.1.0",
        provider="test",
        provider_version="1",
        diagnosis_refs=["a" * 64],
        atomic_edits=[
            AtomicEdit(
                component="prompt",
                target_path=target,
                hypothesis="improve marker",
                expected_metric="success",
                patch=patch,
            )
        ],
        edit_budget=1,
        created_at=datetime.now(timezone.utc),
    )


def test_leakage_critic_rejects_protected_content_and_paths():
    critic = LeakageCritic(protected_values=["SECRET-MARKER"], protected_paths=["evaluator.py", "promotion.py"])
    assert critic.scan(candidate(patch="SECRET-MARKER"))
    assert critic.scan(candidate(target="evaluator.py"))


def test_leakage_critic_rejects_unapproved_capabilities_and_task_maps():
    critic = LeakageCritic()
    assert critic.scan(candidate(patch="import subprocess; subprocess.run('x')"))
    assert critic.scan(candidate(patch='{"p3-task-001":"answer"}'))


def test_leakage_critic_accepts_bounded_skill_config():
    assert LeakageCritic().scan(candidate()) == []
