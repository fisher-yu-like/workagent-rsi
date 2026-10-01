"""Developer-visible feedback and explicit v1 comparison of artifact metrics."""

import json
from pathlib import Path

from .assessment_contracts import RSIFeedback


def build_feedback(develop, *, mode="structured") -> RSIFeedback:
    if develop.get("split") != "develop":
        raise ValueError("only develop feedback can enter candidate context")
    tasks, groups = [], {}
    for row in develop.get("rows", []):
        if row.get("hidden_test"):
            continue
        score = row["score_report"]
        entry = {"task_id": row["task_id"], "acceptance_status": score["acceptance_status"], "quality_score": score["total_score"], "dimension_scores": score["dimension_scores"], "coverage": score["coverage"]}
        issues = [i for i in row["issue_report"]["issues"] if i["feedback_visibility"] == "develop" and i["kind"] == "artifact_defect"]
        if mode == "brief":
            entry["errors"] = [i["requirement_id"] + ": requirement unmet" for i in issues]
        elif mode == "structured":
            entry["issues"] = issues
            for issue in issues:
                key = issue["skill_improvement_hint"] or issue["requirement_id"]
                groups.setdefault(key, []).append(f"{row['task_id']}:{issue['issue_id']}")
        tasks.append(entry)
    return RSIFeedback(mode=mode, tasks=tasks, issue_groups=groups)


def comparison_metrics(baseline, candidate, root, contract):
    splits = set(baseline)
    complete = bool(splits) and splits == set(candidate) and all(r.get("assessment_complete") and r.get("quality_score") is not None for bundle in (baseline, candidate) for r in bundle.values())
    comparable = complete and all(baseline[s]["assessment_identity"] == candidate[s]["assessment_identity"] == contract.assessment_identity and baseline[s]["split_hash"] == candidate[s]["split_hash"] for s in splits)
    metrics = {"assessment_mode": "artifact-v1", "assessment_complete": complete,
        "comparable": comparable, "repeat_agreement": complete and all(r.get("repeat_agreement") for bundle in (baseline, candidate) for r in bundle.values()),
        "evaluation_seconds": sum(r.get("evaluation_seconds", 0) for bundle in (baseline, candidate) for r in bundle.values()),
        "cost_delta": None, "critical_regressions": 0, "quality_delta": None, "success_delta": None,
        "protected_quality_deltas": {}, "issue_changes": {"resolved": 0, "introduced": 0}}
    if not comparable:
        return metrics
    if "develop" not in splits:
        metrics["comparable"] = False
        return metrics
    metrics["quality_delta"] = candidate["develop"]["quality_score"] - baseline["develop"]["quality_score"]
    metrics["success_delta"] = candidate["develop"]["success_rate"] - baseline["develop"]["success_rate"]
    metrics["protected_quality_deltas"] = {s: candidate[s]["quality_score"] - baseline[s]["quality_score"] for s in splits if s != "develop"}
    # Private rows remain on the evaluation side, including hidden requirements.
    for split in splits:
        old = json.loads((Path(root) / "baseline" / split / "evaluation_full.json").read_text(encoding="utf-8"))
        new = json.loads((Path(root) / "candidate" / split / "evaluation_full.json").read_text(encoding="utf-8"))
        old_rows = {r["task_id"]: r for r in old["rows"]}
        for row in new["rows"]:
            previous = old_rows[row["task_id"]]
            before = {c["requirement_id"]: c["status"] for c in previous["score_report"]["criterion_results"]}
            after = {c["requirement_id"]: c["status"] for c in row["score_report"]["criterion_results"]}
            metrics["critical_regressions"] += sum(before[r] == "PASS" and after[r] != "PASS" for r in row["critical_requirements"])
            a = {i["issue_id"] for i in previous["issue_report"]["issues"] if i["kind"] == "artifact_defect"}
            b = {i["issue_id"] for i in row["issue_report"]["issues"] if i["kind"] == "artifact_defect"}
            metrics["issue_changes"]["resolved"] += len(a - b)
            metrics["issue_changes"]["introduced"] += len(b - a)
    return metrics


def decide_artifact(candidate_id, verification, metrics, contract):
    from .hashing import canonical_json_hash
    from .rsi_contracts import PromotionDecision

    t = contract.thresholds
    required = {"quality_gain", "success_tolerance", "protected_quality_tolerance", "max_evaluation_seconds"}
    if not required.issubset(t):
        raise ValueError("artifact-v1 needs explicitly versioned quality/success/protected/cost thresholds")
    gates = {
        "verification": verification.passed,
        "complete": metrics["assessment_complete"], "comparable": metrics["comparable"],
        "quality": metrics["quality_delta"] is not None and metrics["quality_delta"] > t["quality_gain"],
        "success": metrics["success_delta"] is not None and metrics["success_delta"] >= -t["success_tolerance"],
        "critical_regression": metrics["critical_regressions"] == 0,
        "protected_quality": all(v >= -t["protected_quality_tolerance"] for v in metrics["protected_quality_deltas"].values()),
        "observed_repeat_agreement": metrics["repeat_agreement"],
        "measured_evaluation_budget": metrics["evaluation_seconds"] <= t["max_evaluation_seconds"],
    }
    return PromotionDecision(candidate_id=candidate_id, decision="accept" if all(gates.values()) else "reject", gate_results=gates,
        develop_delta=metrics["quality_delta"], cost_delta=None,
        evidence_refs=[canonical_json_hash({"verification": verification.model_dump(mode="json"), "metrics": metrics, "contract": contract.model_dump(mode="json"), "gates": gates})])
