"""T01: independent expected-open cases. Failures are intentional evidence.

No xfail or special collection rules: later owner tasks must make these pass.
All artifacts are generated locally. No model, rendering or external data is used.
"""

import importlib.util
import inspect
import json
from pathlib import Path

from docx import Document
from openpyxl import Workbook
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches

from review_support import observe, requirement, specification
from workagent_rsi.artifact_assessment import assess, spec_from_task
from workagent_rsi.contracts import TaskSpec
from workagent_rsi.harness import Harness
from workagent_rsi.hashing import canonical_json_hash
from workagent_rsi.rsi_contracts import EvaluationContract
from workagent_rsi.workagent_evaluator import WorkAgentFrozenEvaluator
from workagent_rsi.workagent_provider import WorkAgentConfig, WorkAgentSkill


def test_R01_blank_analysis_cannot_receive_full_task_acceptance(tmp_path):
    task = TaskSpec(task_id="R01", domain="excel", instruction=(
        "Read all supplied sales records, aggregate by region, add a chart, "
        "and format totals to two decimal places."
    ))
    path = tmp_path / "blank.xlsx"
    book = Workbook()
    book.save(path)
    book.close()
    spec = spec_from_task(task)
    shared, score, issues = assess(spec, {"output": path})
    observe(tmp_path, "R01", task=task, spec=spec, assessment=shared, score=score, issues=issues)
    assert not (score.acceptance_status == "PASS" and score.total_score == 100), (
        "R01: file readability cannot establish the unmet analysis requirements"
    )


def test_R02_required_paragraph_cannot_match_another_paragraph(tmp_path):
    document = Document()
    document.add_paragraph("Required conclusion")
    document.add_paragraph("Unrelated second paragraph")
    path = tmp_path / "wrong-location.docx"
    document.save(path)
    assert document.paragraphs[1].text == "Unrelated second paragraph"
    spec = specification("word", requirement("text.contains", "Required conclusion", paragraph=2))
    shared, score, issues = assess(spec, {"output": path})
    observe(tmp_path, "R02", spec=spec, assessment=shared, score=score, issues=issues)
    assert shared.checks[0].status != "PASS", "R02: a hit in paragraph 1 does not satisfy paragraph 2"


def test_R03_off_slide_text_cannot_establish_visible_delivery(tmp_path):
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    shape = slide.shapes.add_textbox(deck.slide_width + Inches(1), 0, Inches(2), Inches(1))
    shape.text = "Visible takeaway"
    assert shape.left > deck.slide_width
    path = tmp_path / "off-slide.pptx"
    deck.save(path)
    # The natural-language obligation includes visibility. The legacy text adapter
    # silently omits it. SPEC_INCOMPLETE or NEEDS_REVIEW is acceptable; full PASS is not.
    spec = specification("powerpoint", requirement(
        "powerpoint.texts", ["Visible takeaway"],
        description="Show the takeaway visibly inside slide 1", slide=1,
    ))
    shared, score, issues = assess(spec, {"output": path})
    observe(tmp_path, "R03", spec=spec, assessment=shared, score=score, issues=issues,
            independent_geometry={"left": shape.left, "slide_width": deck.slide_width})
    assert score.acceptance_status != "PASS", "R03: text existence alone cannot establish visible delivery"


def test_R04_opaque_containment_cannot_be_declared_clear(tmp_path):
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    text = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(.5))
    text.text = "Must remain visible"
    cover = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(.5), Inches(.5), Inches(4), Inches(2))
    cover.fill.solid()
    cover.fill.fore_color.rgb = RGBColor(255, 255, 255)
    assert cover.left < text.left and cover.top < text.top
    assert cover.left + cover.width > text.left + text.width
    assert cover.top + cover.height > text.top + text.height
    assert list(slide.shapes)[-1].shape_id == cover.shape_id
    path = tmp_path / "covered.pptx"
    deck.save(path)
    spec = specification("powerpoint", requirement(
        "powerpoint.overlap", [], slide=1,
        description="No foreground opaque object may cover required text",
    ))
    shared, score, issues = assess(spec, {"output": path})
    observe(tmp_path, "R04", spec=spec, assessment=shared, score=score, issues=issues,
            independent_geometry={"covered_text": text.shape_id, "later_opaque_cover": cover.shape_id})
    assert shared.checks[0].status != "PASS", (
        "R04: containment alone is not evidence of an unobscured slide; review is acceptable"
    )


def formula_case(tmp_path, *, allow_equivalent):
    book = Workbook()
    sheet = book.active
    sheet["B2"], sheet["B3"], sheet["B4"] = 4, 6, "=B2+B3"
    path = tmp_path / "sum.xlsx"
    book.save(path)
    book.close()
    req = requirement("excel.formula", "=SUM(B2:B3)", sheet="Sheet", cell="B4",
                      description="Any equivalent summation is allowed" if allow_equivalent else "Use exactly =SUM(B2:B3)")
    if allow_equivalent:
        req = req.model_copy(update={"options": {"formula_policy": "equivalent", "input_variants": [[4, 6], [-3, 9], [0, 0]]}})
    spec = specification("excel", req)
    return spec, path


def test_R05_permitted_equivalent_formula_is_not_rejected_as_string_mismatch(tmp_path):
    # Independent arithmetic for every declared variant; no formula evaluator is used as oracle.
    assert all(a + b == sum([a, b]) for a, b in [(4, 6), (-3, 9), (0, 0)])
    spec, path = formula_case(tmp_path, allow_equivalent=True)
    shared, score, issues = assess(spec, {"output": path})
    observe(tmp_path, "R05", spec=spec, assessment=shared, score=score, issues=issues)
    assert shared.checks[0].status != "FAIL", (
        "R05: allowed equivalence requires semantic validation or an explicit capability/spec gap"
    )


def test_exact_formula_control_rejects_a_different_expression(tmp_path):
    spec, path = formula_case(tmp_path, allow_equivalent=False)
    shared, score, _ = assess(spec, {"output": path})
    assert shared.checks[0].status == "FAIL"
    assert score.acceptance_status == "FAIL"


def test_R09_mixed_pilot_formal_cannot_authorize_a_global_mean(tmp_path):
    module_path = Path(__file__).resolve().parents[1] / "project_artifacts/phase3_experiments/scripts/analyze_formal.py"
    loader = importlib.util.spec_from_file_location("review_formal_analyzer", module_path)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    for mode, value in [("pilot", 0), ("formal", 1)]:
        directory = tmp_path / mode
        directory.mkdir()
        (directory / "summary.json").write_text(json.dumps({
            "mode": mode, "dataset_kind": "external-admitted" if mode == "formal" else "project-generated",
            "claim_boundary": {"external_benchmark": mode == "formal"},
            "experiments": [{"status": "completed", "metrics": {"success": value}}],
        }), encoding="utf-8")
    result = module.analyze_results(tmp_path)
    observe(tmp_path, "R09", analysis=result)
    assert result.get("claims_allowed") is not True and result.get("numeric_means", {}).get("success") != .5, (
        "R09: synthetic mixed identities must not yield a formal global claim or a combined mean"
    )


def test_R10_final_assessment_failure_enters_bounded_repair(tmp_path, monkeypatch):
    calls = []

    class LocalRepairableAdapter:
        def __init__(self, *args, **kwargs):
            pass

        def execute(self, task, skill_id):
            calls.append(task.task_id)
            path = tmp_path / f"attempt-{len(calls)}.docx"
            doc = Document()
            doc.add_paragraph("Required conclusion" if len(calls) > 1 else "Wrong conclusion")
            doc.save(path)
            yield {"kind": "artifact", "artifact_path": str(path), "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}

    monkeypatch.setattr("workagent_rsi.run.WorkAgentOfficeAdapter", LocalRepairableAdapter)
    task = TaskSpec(task_id="R10", domain="word", instruction="Create the required conclusion.",
                    expected_constraints={"required_text": "Required conclusion"})
    harness = Harness(tmp_path / "results", workagent_config=WorkAgentConfig(verify_com=False))
    options = {"max_attempts": 1}
    repair_supported = "repair_policy" in inspect.signature(harness.run).parameters
    if repair_supported:
        from workagent_rsi.repair_loop import RepairPolicy
        options["repair_policy"] = RepairPolicy(max_repairs=1)
    result = harness.run(task, **options)
    observe(tmp_path, "R10", result=result, adapter_calls=calls, repair_policy_supported=repair_supported,
            execution_kind="authored local stub; no model")
    assert len(calls) == 2 and result["state"] == "SUCCEEDED", (
        "R10: final assessment failure needs explicit bounded repair; keep max_attempts as execution retry only"
    )


def test_R11_code_execution_failure_remains_a_develop_learning_signal(tmp_path, monkeypatch):
    task = TaskSpec(task_id="R11", domain="word", instruction="Create the required conclusion.",
                    expected_constraints={"required_text": "Required conclusion"})
    config = WorkAgentConfig(verify_com=False)
    evaluator = WorkAgentFrozenEvaluator(workagent_config=config, input_base=tmp_path, assessment_output_root=tmp_path / "judge")
    split_hash = canonical_json_hash([task.model_dump(mode="json")])
    contract = EvaluationContract(
        contract_id="R11", dataset_hash=split_hash, split_hashes={"develop": split_hash},
        evaluator_hash=evaluator.evaluator_hash, assessment_mode="artifact-v1",
        assessment_identity=evaluator.assessment_identity, acceptance_hashes={task.task_id: spec_from_task(task).fingerprint()},
        provider_policy="workagent-config:" + canonical_json_hash(config.model_dump(mode="json")),
        seeds=[1], repeats=1, timeout_seconds=10, thresholds={}, git_commit="independent-fixture",
    )

    def failed_execution(*args, **kwargs):
        return {"state": "FAILED", "artifacts": [], "failure": {
            "message": "SyntaxError: invalid syntax in authored stub", "retryable": False,
            "failure_origin": "agent_execution",
        }}

    monkeypatch.setattr("workagent_rsi.workagent_evaluator.Harness.run", failed_execution)
    report = evaluator.evaluate_split([task], "develop", WorkAgentSkill(instructions="Read current input"), contract,
                                     tmp_path / "split", reveal_per_task=True)
    observe(tmp_path, "R11", report=report, execution_kind="injected failure; no model or code executed")
    assert report.get("execution_success_rate") == 0 and report.get("execution_failures"), (
        "R11: known code failure needs an explicit failed-task denominator and develop feedback, with unobserved quality null"
    )
