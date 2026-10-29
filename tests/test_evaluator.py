from workagent_rsi.contracts import TaskSpec
from workagent_rsi.evaluator import BasicEvaluator
from workagent_rsi.storage import ArtifactStore


def test_no_keyword_fallback_without_judge(tmp_path):
    ref = ArtifactStore(tmp_path / "files").put_bytes(b"hello", "text/plain")
    task = TaskSpec(
        task_id="t",
        domain="smoke",
        instruction="hello",
        expected_constraints={"required_text": "hello"},
    )
    report = BasicEvaluator(report_root=tmp_path / "reports").evaluate(
        task, [ref], "trace"
    )
    assert not report.passed and report.score is None
    assert report.task_acceptance == "INCOMPLETE"
