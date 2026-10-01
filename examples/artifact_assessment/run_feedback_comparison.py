"""Run the three feedback arms with identical tasks, initial config and edit budget."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

from workagent_rsi.artifact_assessment import SharedAssessment, spec_from_task
from workagent_rsi.artifact_candidate import ArtifactFeedbackProvider
from workagent_rsi.candidate_workspace import CandidateWorkspaceBuilder
from workagent_rsi.contracts import TaskSpec
from workagent_rsi.frozen_evaluator import FrozenEvaluator
from workagent_rsi.hashing import canonical_json_hash
from workagent_rsi.promotion import PromotionController
from workagent_rsi.registry import SkillRegistry
from workagent_rsi.rsi_contracts import EvaluationContract
from workagent_rsi.rsi_loop import RSILoop
from workagent_rsi.verifier import CandidateVerifier, VerificationPolicy


def verifier_runner(command, cwd, timeout):
    if command[:2] == ["py", "-3.12"]:
        command = [sys.executable, *command[2:]]
    return subprocess.run(command, cwd=cwd, timeout=timeout, capture_output=True, text=True)


def task(input_root, task_id, records, *, hidden=False):
    source = input_root / f"{task_id}.json"
    source.write_text(json.dumps(records), encoding="utf-8")
    return TaskSpec(task_id=task_id, domain="excel", instruction="Summarize every input sales row by region with chart and two-decimal totals.",
                    input_files=(str(source.resolve()),), expected_constraints={"sales_summary": True}, hidden_test=hidden)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("output must be absent or empty")
    args.output.mkdir(parents=True, exist_ok=True)
    inputs = args.output / "inputs"
    inputs.mkdir()
    tasks = {
        "develop": [task(inputs, "develop-sales", [{"region": "East", "amount": 10}, {"region": "West", "amount": 20}, {"region": "East", "amount": 5}])],
        "regression": [task(inputs, "regression-sales", [{"region": "North", "amount": 7}, {"region": "South", "amount": 9}])],
        "hidden": [task(inputs, "hidden-sales", [{"region": "PRIVATE", "amount": 1234}, {"region": "PRIVATE", "amount": 4321}], hidden=True)],
    }
    split_hashes = {split: canonical_json_hash([t.model_dump(mode="json") for t in rows]) for split, rows in tasks.items()}
    assessment_identity = SharedAssessment().identity()
    contract = EvaluationContract(contract_id="artifact-v1-feedback-comparison", dataset_hash=canonical_json_hash(split_hashes),
        split_hashes=split_hashes, evaluator_hash=assessment_identity, assessment_mode="artifact-v1",
        assessment_identity=assessment_identity,
        acceptance_hashes={t.task_id: spec_from_task(t).fingerprint() for rows in tasks.values() for t in rows},
        provider_policy="offline-bounded", seeds=[20260930], repeats=2, timeout_seconds=60,
        thresholds={"quality_gain": .01, "success_tolerance": 0, "protected_quality_tolerance": 0, "max_evaluation_seconds": 60}, git_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip())
    initial = {"sales_rows": "omit_last", "sales_chart": False, "sales_number_format": False}
    summary = {"claim_boundary": "project-generated offline bounded-provider engineering comparison", "edit_budget": 3, "rounds": 1, "arms": {}}
    for mode in ("score_only", "brief", "structured"):
        root = args.output / mode
        registry = SkillRegistry(root / "registry")
        registry.register(skill_id="office.sales", version="0.1.0", package=initial, manifest={"domain": "excel"}, status="champion", evidence_refs=["a" * 64], parent_version=None, candidate_id=None)
        source = root / "source"
        source.mkdir(parents=True)
        (source / "skill.json").write_text(json.dumps(initial), encoding="utf-8")
        loop = RSILoop(registry=registry, workspace_builder=CandidateWorkspaceBuilder(), provider=ArtifactFeedbackProvider(),
            verifier=CandidateVerifier(runner=verifier_runner), evaluator=FrozenEvaluator(assessment_identity),
            promotion=PromotionController(), feedback_mode=mode)
        result = loop.run(skill_id="office.sales", tasks_by_split=tasks, contract=contract, source_root=source,
            run_root=root / "run", verification_policy=VerificationPolicy(allowed_targets={"skill.json"}), rounds=1, edit_budgets=[3])
        summary["arms"][mode] = {"status": result["status"], "initial_develop_score": result["metrics"]["initial_develop_score"],
            "final_develop_score": result["metrics"]["final_develop_score"], "champion_version": result["champion_version"],
            "decision": result["rounds"][0]["decision"]["decision"], "actual_edit_count": result["rounds"][0]["actual_edit_count"],
            "run_summary": str((root / "run" / "run_summary.json").resolve())}
    (args.output / "comparison.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
