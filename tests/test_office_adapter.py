from pathlib import Path

from workagent_rsi.contracts import TaskSpec
from workagent_rsi.executor import LocalOfficeAdapter


def test_local_office_adapter_creates_real_artifact(tmp_path: Path):
    task = TaskSpec(
        task_id="excel-task",
        domain="excel",
        instruction="Create a workbook",
        expected_constraints={"required_text": "MARKER-001"},
    )
    events = list(LocalOfficeAdapter(tmp_path).execute(task, "b0.office.local"))
    artifact = events[-1]
    path = Path(artifact["artifact_path"])
    assert artifact["kind"] == "artifact"
    assert path.suffix == ".xlsx"
    assert path.stat().st_size > 0


def test_local_office_adapter_rejects_unknown_domain(tmp_path: Path):
    task = TaskSpec(task_id="bad", domain="pdf", instruction="Create", expected_constraints={})
    events = list(LocalOfficeAdapter(tmp_path).execute(task, "b0.office.local"))
    assert events[-1]["kind"] == "failure"
    assert events[-1]["retryable"] is False


def test_local_office_adapter_rejects_path_like_task_id(tmp_path: Path):
    task = TaskSpec(task_id="..\\escape", domain="word", instruction="Create")
    events = list(LocalOfficeAdapter(tmp_path).execute(task, "b0.office.local"))
    assert events[-1]["kind"] == "failure"
    assert "task_id" in events[-1]["message"]
