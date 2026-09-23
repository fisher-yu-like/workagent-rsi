from pathlib import Path

from workagent_rsi.contracts import TaskSpec
from workagent_rsi.evaluator import BasicEvaluator
from workagent_rsi.storage import ArtifactStore


def test_evaluator_passes_required_text(tmp_path: Path):
    artifacts = ArtifactStore(tmp_path / "artifacts")
    ref = artifacts.put_bytes(b"hello", "text/plain")
    task = TaskSpec(
        task_id="t1",
        domain="smoke",
        instruction="hello",
        expected_constraints={"required_text": "hello"},
    )
    report = BasicEvaluator().evaluate(task, [ref], "trace-1")
    assert report.passed is True
    assert report.critical_failures == []


def test_evaluator_fails_missing_required_text(tmp_path: Path):
    artifacts = ArtifactStore(tmp_path / "artifacts")
    ref = artifacts.put_bytes(b"goodbye", "text/plain")
    task = TaskSpec(
        task_id="t1",
        domain="smoke",
        instruction="hello",
        expected_constraints={"required_text": "hello"},
    )
    report = BasicEvaluator().evaluate(task, [ref], "trace-1")
    assert report.passed is False
    assert report.critical_failures

