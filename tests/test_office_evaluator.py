from pathlib import Path

from workagent_rsi.contracts import TaskSpec
from workagent_rsi.evaluator import OfficeArtifactEvaluator
from workagent_rsi.executor import LocalOfficeAdapter
from workagent_rsi.storage import ArtifactStore
from workagent_rsi.orchestrator import Orchestrator
from workagent_rsi.storage import TraceStore


def test_office_evaluator_reopens_generated_workbook(tmp_path: Path):
    task = TaskSpec(
        task_id="excel-task",
        domain="excel",
        instruction="Create a workbook",
        expected_constraints={"required_text": "MARKER-001"},
    )
    adapter = LocalOfficeAdapter(tmp_path / "generated")
    events = list(adapter.execute(task, "b0.office.local"))
    ref_store = ArtifactStore(tmp_path / "artifacts")
    ref = ref_store.put_file(Path(events[-1]["artifact_path"]), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml")
    report = OfficeArtifactEvaluator().evaluate(task, [ref], "trace-1")
    assert report.passed is True
    assert report.dimensions["format_validity"] == 1.0


def test_orchestrator_accepts_binary_office_artifact(tmp_path: Path):
    task = TaskSpec(task_id="word-task", domain="word", instruction="Create a document", expected_constraints={"required_text": "MARKER-002"})
    result = Orchestrator(
        artifact_store=ArtifactStore(tmp_path / "artifacts"),
        trace_store=TraceStore(tmp_path / "trace.db"),
        adapter=LocalOfficeAdapter(tmp_path / "generated"),
        evaluator=OfficeArtifactEvaluator(),
    ).run(task, "b0.office.local")
    assert result["state"] == "SUCCEEDED"
