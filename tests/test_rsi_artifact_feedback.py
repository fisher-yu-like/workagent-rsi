import json
from pathlib import Path
import subprocess
import sys

import pytest

from workagent_rsi.artifact_assessment import SharedAssessment, spec_from_task
from workagent_rsi.artifact_candidate import ArtifactFeedbackProvider
from workagent_rsi.candidate_provider import CodexCandidateProvider
from workagent_rsi.candidate_workspace import CandidateWorkspaceBuilder
from workagent_rsi.frozen_evaluator import FrozenEvaluator
from workagent_rsi.hashing import canonical_json_hash
from workagent_rsi.promotion import PromotionController
from workagent_rsi.registry import SkillRegistry
from workagent_rsi.rsi_contracts import EvaluationContract
from workagent_rsi.rsi_feedback import build_feedback
from workagent_rsi.rsi_loop import RSILoop
from workagent_rsi.skill_runtime import PilotSkillConfig
from workagent_rsi.verifier import CandidateVerifier, VerificationPolicy
from test_artifact_assessment_excel import sales_task


def portable_verification(command, cwd, timeout):
    # Existing runner injection preserves CandidateVerifier's meaning and real subprocess checks.
    if command[:2] == ["py", "-3.12"]:
        command = [sys.executable, *command[2:]]
    return subprocess.run(command, cwd=cwd, timeout=timeout, capture_output=True, text=True)


def setup_loop(root, *, provider=None, config=None, mode="structured", unknown=False):
    tasks = {
        "develop": [sales_task(root / "input", "dev")],
        "regression": [sales_task(root / "input", "reg", [{"region": "North", "amount": 7}, {"region": "South", "amount": 9}])],
        "hidden": [sales_task(root / "input", "secret", [{"region": "PRIVATE_REGION", "amount": 1234}, {"region": "PRIVATE_REGION", "amount": 4321}], hidden=True)],
    }
    if unknown:
        from workagent_rsi.assessment_contracts import Requirement, Location
        task = tasks["develop"][0]
        spec = spec_from_task(task).model_dump()
        spec["requirements"].append(Requirement(requirement_id="visual", description="legibility", check="visual", location=Location(artifact="output"), dimension="presentation", evidence_source="real render").model_dump())
        tasks["develop"] = [task.model_copy(update={"expected_constraints": {"acceptance_spec": spec}})]
    hashes = {s: canonical_json_hash([t.model_dump(mode="json") for t in rows]) for s, rows in tasks.items()}
    identity = SharedAssessment().identity()
    contract = EvaluationContract(contract_id="artifact-v1-test", dataset_hash=canonical_json_hash(hashes), split_hashes=hashes,
        evaluator_hash=identity, assessment_mode="artifact-v1", assessment_identity=identity,
        acceptance_hashes={t.task_id: spec_from_task(t).fingerprint() for rows in tasks.values() for t in rows},
        provider_policy="offline-bounded", seeds=[1], repeats=2, timeout_seconds=60,
        thresholds={"quality_gain": .01, "success_tolerance": 0, "protected_quality_tolerance": 0, "max_evaluation_seconds": 60}, git_commit="test")
    registry = SkillRegistry(root / "registry")
    package = config or {"sales_rows": "omit_last", "sales_chart": False, "sales_number_format": False}
    registry.register(skill_id="office.sales", version="0.1.0", package=package, manifest={"domain": "excel"}, status="champion", evidence_refs=["a" * 64], parent_version=None, candidate_id=None)
    source = root / "source"
    source.mkdir()
    (source / "skill.json").write_text(json.dumps(package), encoding="utf-8")
    loop = RSILoop(registry=registry, workspace_builder=CandidateWorkspaceBuilder(), provider=provider or ArtifactFeedbackProvider(),
        verifier=CandidateVerifier(runner=portable_verification), evaluator=FrozenEvaluator(identity), promotion=PromotionController(), feedback_mode=mode)
    arguments = dict(skill_id="office.sales", tasks_by_split=tasks, contract=contract, source_root=source, run_root=root / "run", verification_policy=VerificationPolicy(allowed_targets={"skill.json"}))
    return loop, arguments


def test_feedback_changes_execution_and_both_sides_have_two_reports(tmp_path):
    loop, args = setup_loop(tmp_path)
    result = loop.run(**args, rounds=2)
    assert result["status"] == "completed", result.get("failure")
    assert result["rounds"][0]["decision"]["decision"] == "accept"
    assert "artifact_execution_config" in result["rounds"][0]["verification"]["executed_checks"]
    assert result["metrics"]["final_develop_score"] == 1
    assert result["rounds"][0]["metrics"]["repeat_agreement"] is True
    assert result["rounds"][0]["metrics"]["cost_delta"] is None
    assert result["rounds"][1]["decision"]["decision"] == "reject"
    round_root = args["run_root"] / "round-01"
    for side in ("baseline", "candidate"):
        for report in ("score.json", "issues.json"):
            assert (round_root / side / "develop/dev/repeat-1/assessment" / report).exists()
    context = (round_root / "candidate_workspace/artifact_feedback.json").read_text()
    assert "PRIVATE_REGION" not in context and "4321" not in context and "secret" not in context
    assert "Summary" in context and "sales_rows=all" in context
    assert "rows" not in result["rounds"][0]["baseline"]["hidden"]


class RegressingProvider(ArtifactFeedbackProvider):
    def generate_with_feedback(self, workspace, feedback, parent_version, edit_budget, record_root):
        candidate, record = super().generate_with_feedback(workspace, feedback, parent_version, edit_budget, record_root)
        edit = candidate.atomic_edits[0].model_copy(update={"patch": '{"sales_rows":"omit_last"}'})
        return candidate.model_copy(update={"atomic_edits": [edit]}), record


def test_rejected_candidate_score_never_replaces_retained_version(tmp_path):
    loop, args = setup_loop(tmp_path, provider=RegressingProvider(), config={"sales_rows": "all", "sales_chart": True, "sales_number_format": True})
    result = loop.run(**args, rounds=1)
    assert result["status"] == "completed", result.get("failure")
    assert result["rounds"][0]["decision"]["decision"] == "reject"
    assert result["rounds"][0]["metrics"]["critical_regressions"] > 0
    assert result["rounds"][0]["candidate_reports"]["develop"]["quality_score"] < 1
    assert result["champion_version"] == "0.1.0"
    assert result["metrics"]["final_develop_score"] == 1


def test_incomplete_assessment_stops_before_candidate(tmp_path):
    loop, args = setup_loop(tmp_path, unknown=True)
    result = loop.run(**args, rounds=1)
    assert result["status"] == "incomplete", result.get("failure")
    assert result["incomplete_round"]["status"] == "unavailable"
    assert not (args["run_root"] / "round-01/candidate_workspace").exists()
    assert loop.registry.champion("office.sales").version == "0.1.0"


def test_passing_low_quality_tasks_enter_feedback(tmp_path):
    loop, args = setup_loop(tmp_path, config={"sales_rows": "all", "sales_chart": False, "sales_number_format": True})
    result = loop.run(**args, rounds=1)
    assert result["status"] == "completed", result.get("failure")
    feedback = json.loads((args["run_root"] / "round-01/develop_feedback.json").read_text())
    assert feedback["tasks"][0]["acceptance_status"] == "PASS"
    assert feedback["tasks"][0]["issues"][0]["requirement_id"] == "chart"
    assert result["rounds"][0]["decision"]["decision"] == "accept"


def test_reserved_feedback_refused_and_unknown_tasks_stay_in_denominator(tmp_path):
    with pytest.raises(ValueError, match="develop"):
        build_feedback({"split": "hidden", "rows": []})
    loop, args = setup_loop(tmp_path, unknown=True)
    report = loop.evaluator.evaluate_split(args["tasks_by_split"]["develop"], "develop", PilotSkillConfig(), args["contract"], tmp_path / "assess")
    assert report["task_count"] == 1
    assert report["quality_score"] is None
    assert report["success_rate"] is None
    assert report["coverage"] < 1


def test_checkpoint_refuses_new_feedback_mode_and_changed_input(tmp_path):
    loop, args = setup_loop(tmp_path)
    result = loop.run(**args, rounds=1)
    assert result["status"] == "completed", result.get("failure")
    loop.feedback_mode = "brief"
    with pytest.raises(ValueError, match="feedback_mode"):
        loop.run(**args, rounds=1, resume_root=args["run_root"])
    loop.feedback_mode = "structured"
    source = Path(args["tasks_by_split"]["develop"][0].input_files[0])
    source.write_text('[{"region":"East","amount":99}]', encoding="utf-8")
    with pytest.raises(ValueError, match="identity changed"):
        loop.run(**args, rounds=1, resume_root=args["run_root"])


def test_codex_new_prompt_consumes_feedback_without_fixed_marker_patch():
    from workagent_rsi.assessment_contracts import RSIFeedback
    feedback = RSIFeedback(tasks=[{"task_id": "dev", "issues": [{"location": "Summary!B2", "observed": 10, "expected": 15}]}])
    prompt = CodexCandidateProvider._artifact_prompt(feedback, "0.1.0", 2)
    assert "Summary!B2" in prompt
    assert "sales_rows" in prompt
    assert 'exactly {"marker_source"' not in prompt


def test_same_budget_feedback_comparison_favors_structured_evidence(tmp_path):
    outcomes = {}
    for mode in ("score_only", "brief", "structured"):
        loop, args = setup_loop(tmp_path / mode, mode=mode)
        result = loop.run(**args, rounds=1, edit_budgets=[3])
        assert result["status"] == "completed", result.get("failure")
        outcomes[mode] = {
            "initial": result["metrics"]["initial_develop_score"],
            "final": result["metrics"]["final_develop_score"],
            "edits": result["rounds"][0]["actual_edit_count"],
            "rounds": result["round_count"],
        }
    assert len({item["initial"] for item in outcomes.values()}) == 1
    assert all(item["rounds"] == 1 and item["edits"] <= 3 for item in outcomes.values())
    assert outcomes["structured"]["final"] > outcomes["brief"]["final"] > outcomes["score_only"]["final"]
