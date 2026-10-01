import json

import pytest
from openpyxl import load_workbook

from workagent_rsi.artifact_assessment import assess
from workagent_rsi.assessment_contracts import AcceptanceSpec, Requirement, Location
from workagent_rsi.contracts import TaskSpec
from workagent_rsi.sales_assessment import sales_spec
from workagent_rsi.skill_runtime import PilotSkillConfig, SkillConfiguredOfficeAdapter


def sales_task(root, task_id="sales", records=None, hidden=False):
    root.mkdir(parents=True, exist_ok=True)
    source = root / f"{task_id}.json"
    source.write_text(json.dumps(records or [{"region": "East", "amount": 10}, {"region": "West", "amount": 20}, {"region": "East", "amount": 5}]), encoding="utf-8")
    return TaskSpec(task_id=task_id, domain="excel", instruction="Summarize all input sales by region with a chart and two-decimal totals.", input_files=(str(source),), expected_constraints={"sales_summary": True}, hidden_test=hidden)


def produce(root, task, **config):
    events = list(SkillConfiguredOfficeAdapter(root, PilotSkillConfig(**config)).execute(task, "office.sales"))
    return events[-1]["artifact_path"]


def test_correct_partial_and_wrong_real_workbooks(tmp_path):
    task = sales_task(tmp_path)
    spec = sales_spec(task)
    correct = produce(tmp_path / "correct", task)
    partial = produce(tmp_path / "partial", task, sales_chart=False)
    wrong = produce(tmp_path / "wrong", task, sales_rows="omit_last", sales_chart=False, sales_number_format=False)
    reports = [assess(spec, {"output": p}) for p in (correct, partial, wrong)]
    assert [r[1].total_score for r in reports] == [100, 87.5, 52.5]
    assert [r[1].acceptance_status for r in reports] == ["PASS", "PASS", "FAIL"]
    totals = {r.requirement_id: r.expected for r in spec.requirements if r.requirement_id.startswith("total.")}
    assert totals == {"total.East": 15, "total.West": 20}  # independent literal oracle
    issue = next(i for i in reports[-1][2].issues if i.requirement_id == "total.East")
    assert (issue.location.sheet, issue.location.cell, issue.observed, issue.expected) == ("Summary", "B2", 10, 15)
    assert issue.cause_hypothesis is None
    assert "sales_rows=all" in issue.skill_improvement_hint


def test_cached_value_is_not_recalculation_and_incomplete_keeps_known_dimensions(tmp_path):
    task = sales_task(tmp_path)
    path = produce(tmp_path / "artifact", task)
    spec = sales_spec(task)
    payload = spec.model_dump()
    payload["requirements"].append(Requirement(requirement_id="cache", description="cached formula result", check="excel.cached_value", location=Location(artifact="output", sheet="Summary", cell="C2"), expected=15, critical=True, dimension="correctness", evidence_source="independent input sum").model_dump())
    _, score, issues = assess(AcceptanceSpec.model_validate(payload), {"output": path})
    assert score.total_score is None
    assert score.dimension_scores["presentation"] == 100
    assert score.acceptance_status == "INCOMPLETE"
    assert issues.issues[0].kind == "assessment_gap"


def test_critical_failure_remains_failure_with_unavailable_check(tmp_path):
    task = sales_task(tmp_path)
    path = produce(tmp_path / "artifact", task, sales_rows="omit_last")
    payload = sales_spec(task).model_dump()
    payload["requirements"].append(Requirement(requirement_id="visual", description="legibility", check="visual", location=Location(artifact="output"), expected="readable", dimension="presentation", evidence_source="rendered image").model_dump())
    _, score, _ = assess(AcceptanceSpec.model_validate(payload), {"output": path})
    assert score.total_score is None
    assert score.acceptance_status == "FAIL"


def test_frozen_input_change_refused_and_issue_id_stable(tmp_path):
    task = sales_task(tmp_path)
    spec = sales_spec(task)
    path = produce(tmp_path / "artifact", task, sales_chart=False)
    first = assess(spec, {"output": path})[2].issues[0]
    second = assess(spec, {"output": path})[2].issues[0]
    assert first.issue_id == second.issue_id
    from pathlib import Path
    Path(task.input_files[0]).write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="input changed"):
        assess(spec, {"output": path})


def test_checker_exception_not_artifact_failure_and_nonapplicable_is_explicit(tmp_path):
    task = sales_task(tmp_path)
    path = produce(tmp_path / "artifact", task)
    data = sales_spec(task).model_dump()
    data["requirements"].extend([
        Requirement(requirement_id="bad_config", description="invalid cell config", check="excel.cell", location=Location(artifact="output", sheet="Summary", cell="!"), expected=1, dimension="correctness", evidence_source="fixture").model_dump(),
        Requirement(requirement_id="na", description="task does not require PDF", check="pdf", location=Location(artifact="output"), applicable=False, dimension="correctness", evidence_source="fixture").model_dump(),
    ])
    shared, score, _ = assess(AcceptanceSpec.model_validate(data), {"output": path})
    assert shared.checks[-2].status == "ERROR"
    assert shared.checks[-1].status == "NOT_APPLICABLE"
    assert score.total_score is None
    assert score.coverage.applicable == len(shared.checks) - 1
