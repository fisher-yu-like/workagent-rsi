"""Task-review entrypoints and transport contracts."""

import json
from pathlib import Path
import subprocess
import sys

from openpyxl import Workbook
import pytest

from workagent_rsi.artifact_assessment import SharedAssessment
from workagent_rsi.check import Check
from workagent_rsi.contracts import TaskSpec
from test_llm_task_review import Provider


@pytest.mark.parametrize(
    "skill", ["evaluator/scripts/evaluate.py", "verifier/scripts/verify.py"]
)
def test_entrypoints_read_task_without_rules_and_leave_missing_judge_incomplete(
    tmp_path, skill
):
    book = Workbook()
    p = tmp_path / "output.xlsx"
    book.save(p)
    task = TaskSpec(task_id="t", domain="excel", instruction="Review the file.")
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "task": task.model_dump(mode="json"),
                "artifacts": {"output": "output.xlsx"},
            }
        )
    )
    process = subprocess.run(
        [
            sys.executable,
            str(Path("skills") / ("office-artifact-" + skill)),
            str(request),
            "--output",
            str(tmp_path / "reports"),
        ],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    report = json.loads((tmp_path / "reports" / "score.json").read_text())
    assert report["task_acceptance"] == "INCOMPLETE" and report["total_score"] is None


def test_check_and_harness_share_task_review_identity(tmp_path):
    from test_llm_task_review import workbook
    from test_assessment_entrypoint_parity import ref
    from workagent_rsi.harness_artifact_evaluator import HarnessArtifactEvaluator

    task = TaskSpec(task_id="t", domain="excel", instruction="Review the file.")
    engine = SharedAssessment(provider=Provider())
    path = workbook(tmp_path)
    a = Check(artifact_assessment=engine, report_root=tmp_path / "check").evaluate(
        task, [ref(path)], "trace"
    )
    b = HarnessArtifactEvaluator(tmp_path / "harness", assessment=engine).evaluate(
        task, [ref(path)], "trace"
    )
    assert a.assessment_identity == b.assessment_identity and a.score == b.score
    assert a.task_acceptance == b.task_acceptance == "PASS"
