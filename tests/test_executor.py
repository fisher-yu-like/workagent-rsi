from workagent_rsi.contracts import TaskSpec
from workagent_rsi.executor import MockWorkAgentAdapter


def test_mock_executor_emits_artifact_event():
    task = TaskSpec(task_id="t1", domain="smoke", instruction="hello")
    events = list(MockWorkAgentAdapter().execute(task, "smoke.echo"))
    assert events[-1]["kind"] == "artifact"
    assert events[-1]["content"] == "hello"


def test_mock_executor_can_emit_controlled_failure():
    task = TaskSpec(task_id="fail", domain="smoke", instruction="fail")
    events = list(MockWorkAgentAdapter().execute(task, "smoke.echo"))
    assert events[-1]["kind"] == "failure"
    assert events[-1]["retryable"] is False

