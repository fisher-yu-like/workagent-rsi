from pathlib import Path

from workagent_rsi.contracts import TaskSpec
from workagent_rsi.evaluator import BasicEvaluator
from workagent_rsi.executor import MockWorkAgentAdapter
from workagent_rsi.orchestrator import Orchestrator
from workagent_rsi.storage import ArtifactStore, TraceStore


def make_orchestrator(tmp_path: Path) -> Orchestrator:
    return Orchestrator(
        artifact_store=ArtifactStore(tmp_path / "artifacts"),
        trace_store=TraceStore(tmp_path / "trace.db"),
        adapter=MockWorkAgentAdapter(),
        evaluator=BasicEvaluator(),
    )


def test_orchestrator_runs_success_task(tmp_path: Path):
    result = make_orchestrator(tmp_path).run(
        TaskSpec(task_id="ok", domain="smoke", instruction="hello", expected_constraints={"required_text": "hello"}),
        "smoke.echo",
    )
    assert result["state"] == "SUCCEEDED"
    assert result["evaluation"]["passed"] is True
    assert result["artifacts"]


def test_orchestrator_records_controlled_failure(tmp_path: Path):
    result = make_orchestrator(tmp_path).run(
        TaskSpec(task_id="fail", domain="smoke", instruction="fail"),
        "smoke.echo",
    )
    assert result["state"] == "FAILED"
    assert result["failure"]["message"] == "controlled failure"
    assert result["run_id"]


def test_orchestrator_retries_transient_failure_with_bounded_attempts(tmp_path: Path):
    result = make_orchestrator(tmp_path).run(
        TaskSpec(task_id="timeout", domain="smoke", instruction="timeout"),
        "smoke.echo",
        max_attempts=2,
    )
    assert result["state"] == "FAILED"
    assert result["failure"]["attempts"] == 2
