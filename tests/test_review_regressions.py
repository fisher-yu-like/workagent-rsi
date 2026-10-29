"""T01: independent expected-open cases. Failures are intentional evidence.

No xfail or special collection rules: later owner tasks must make these pass.
All artifacts are generated locally. No model, rendering or external data is used.
"""

import importlib.util
import json
from pathlib import Path

from openpyxl import Workbook

from review_support import observe, requirement, specification
from workagent_rsi.artifact_assessment import assess, spec_from_task
from workagent_rsi.contracts import TaskSpec
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
