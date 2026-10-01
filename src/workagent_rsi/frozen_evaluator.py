from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Sequence

from .contracts import TaskSpec
from .evaluator import OfficeArtifactEvaluator
from .hashing import canonical_json_hash
from .path_safety import validated_task_directory
from .rsi_contracts import EvaluationContract
from .skill_runtime import PilotSkillConfig, SkillConfiguredOfficeAdapter
from .storage import ArtifactStore


class FrozenEvaluator:
    def __init__(self, evaluator_hash: str, *, assessment=None) -> None:
        self.evaluator_hash = evaluator_hash
        self.assessment = assessment

    def evaluate_split(
        self,
        tasks: Sequence[TaskSpec],
        split_name: str,
        config: PilotSkillConfig,
        contract: EvaluationContract,
        result_root: str | Path,
        *,
        reveal_per_task: bool = True,
    ) -> dict:
        rows_payload = [task.model_dump(mode="json") for task in tasks]
        observed_split_hash = canonical_json_hash(rows_payload)
        if contract.split_hashes.get(split_name) != observed_split_hash:
            raise ValueError("split hash does not match frozen evaluation contract")
        if contract.evaluator_hash != self.evaluator_hash:
            raise ValueError("evaluator hash does not match frozen evaluation contract")
        if contract.assessment_mode == "artifact-v1":
            return self._assess_split(tasks, split_name, config, contract, result_root, reveal_per_task=reveal_per_task)
        root = Path(result_root)
        root.mkdir(parents=True, exist_ok=True)
        rows: list[dict] = []
        for task in tasks:
            task_root = validated_task_directory(root, task.task_id)
            events = list(SkillConfiguredOfficeAdapter(task_root / "generated", config).execute(task, "office.marker"))
            final = events[-1]
            if final["kind"] != "artifact":
                rows.append({"task_id": task.task_id, "passed": False, "failure": final.get("message")})
                continue
            store = ArtifactStore(task_root / "artifacts")
            ref = store.put_file(final["artifact_path"], final["media_type"])
            report = OfficeArtifactEvaluator().evaluate(task, [ref], f"eval-{task.task_id}")
            rows.append(
                {
                    "task_id": task.task_id,
                    "domain": task.domain,
                    "passed": report.passed,
                    "score": report.score,
                    "artifact_id": ref.artifact_id,
                    "critical_failures": report.critical_failures,
                    "warnings": report.warnings,
                    "dimensions": report.dimensions,
                    "channel_status": report.channel_status,
                    "evidence": report.evidence,
                }
            )
        score = sum(float(row.get("score", 0.0)) for row in rows) / len(rows) if rows else 0.0
        full_report = {
            "split": split_name,
            "task_count": len(rows),
            "success_count": sum(bool(row.get("passed")) for row in rows),
            "score": score,
            "split_hash": observed_split_hash,
            "evaluator_hash": self.evaluator_hash,
            "rows": rows,
        }
        (root / "evaluation_full.json").write_text(json.dumps(full_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        public_report = {key: value for key, value in full_report.items() if key != "rows"}
        if reveal_per_task:
            public_report["rows"] = rows
        (root / "evaluation_public.json").write_text(json.dumps(public_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return public_report

    def _assess_split(self, tasks, split_name, config, contract, result_root, *, reveal_per_task):
        from .artifact_assessment import SharedAssessment, save_reports, spec_from_task
        from .artifact_evaluator import ArtifactEvaluator
        from .artifact_verifier import ArtifactVerifier

        inspector = self.assessment or SharedAssessment()
        if contract.assessment_identity != inspector.identity():
            raise ValueError("artifact assessment identity does not match contract")
        specs = {task.task_id: spec_from_task(task) for task in tasks}
        for task_id, spec in specs.items():
            if contract.acceptance_hashes.get(task_id) != spec.fingerprint():
                raise ValueError("acceptance specification does not match frozen contract")
        root = Path(result_root)
        root.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        rows = []
        repeat_agreement = []
        for task in tasks:
            task_root = validated_task_directory(root, task.task_id)
            repeats = []
            for repeat in range(contract.repeats):
                attempt = task_root / f"repeat-{repeat+1}"
                failure = None
                try:
                    events = list(SkillConfiguredOfficeAdapter(attempt / "generated", config).execute(task, "office.sales"))
                    final = events[-1]
                    paths = {"output": final["artifact_path"]} if final["kind"] == "artifact" else {}
                    failure = final.get("message")
                except Exception as exc:
                    paths, failure = {}, f"{type(exc).__name__}: {exc}"
                shared = inspector.inspect(specs[task.task_id], paths)
                score = ArtifactEvaluator().evaluate(shared)
                issues = ArtifactVerifier().verify(shared)
                save_reports(attempt / "assessment", shared, score, issues)
                row = {"task_id": task.task_id, "domain": task.domain, "hidden_test": task.hidden_test,
                    "passed": score.acceptance_status == "PASS", "score": None if score.total_score is None else score.total_score / 100,
                    "assessment_complete": all(c.status in {"PASS", "PARTIAL", "FAIL", "NOT_APPLICABLE"} for c in shared.checks),
                    "score_report": score.model_dump(mode="json"), "issue_report": issues.model_dump(mode="json"),
                    "critical_requirements": [r.requirement_id for r in shared.spec.requirements if r.critical and r.applicable],
                    "failure": failure, "evidence_path": str((attempt / "assessment").resolve()), "telemetry": shared.telemetry}
                repeats.append(row)
            # Compare actual repeated observations, not merely the candidate verifier outcome.
            model_requirements = {r.requirement_id for r in specs[task.task_id].requirements if r.check in {"semantic", "visual"}}
            def signature(row):
                return {"score": row["score"], "passed": row["passed"], "checks": [(c["requirement_id"], c["status"], c["completion"] if c["requirement_id"] in model_requirements else c["observed"]) for c in row["score_report"]["criterion_results"]]}
            model_used = any(row["telemetry"].get(channel) for row in repeats for channel in ("visual", "semantic"))
            independent = not model_used or all(
                all(item.get("model_calls", 0) > 0 for channel in ("visual", "semantic") for item in row["telemetry"].get(channel, []))
                for row in repeats)
            agreement = len(repeats) >= 2 and independent and all(signature(row) == signature(repeats[0]) for row in repeats[1:])
            repeat_agreement.append(agreement)
            rows.append({**repeats[0], "repeat_count": len(repeats), "repeat_agreement": agreement})
        complete = bool(rows) and all(row["assessment_complete"] for row in rows)
        quality = sum(row["score"] for row in rows) / len(rows) if rows and all(row["score"] is not None for row in rows) else None
        dimensions = sorted({d for row in rows for d in row["score_report"]["dimension_scores"]})
        dimension_scores = {}
        for dimension in dimensions:
            applicable = [row["score_report"]["dimension_scores"][dimension] for row in rows if dimension in row["score_report"]["dimension_scores"]]
            dimension_scores[dimension] = None if any(v is None for v in applicable) else sum(applicable) / len(applicable) / 100
        report = {"split": split_name, "task_count": len(rows), "success_count": sum(row["passed"] for row in rows),
            "success_rate": sum(row["passed"] for row in rows) / len(rows) if complete else None,
            "score": quality, "quality_score": quality, "dimension_scores": dimension_scores,
            "coverage": sum(row["score_report"]["coverage"]["ratio"] for row in rows) / len(rows) if rows else 0,
            "assessment_complete": complete, "repeat_agreement": bool(rows) and all(repeat_agreement),
            "evaluation_seconds": time.perf_counter() - started, "assessment_mode": "artifact-v1",
            "assessment_identity": inspector.identity(), "evaluator_hash": self.evaluator_hash,
            "split_hash": contract.split_hashes[split_name], "rows": rows}
        (root / "evaluation_full.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        public = {k: v for k, v in report.items() if k != "rows"}
        if reveal_per_task and split_name != "hidden":
            public["rows"] = [row for row in rows if not row["hidden_test"]]
        (root / "evaluation_public.json").write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
        return public


class ResponseJudge:
    """Automated response-only channel, separate from Office package reopening."""

    def evaluate(self, tasks: Sequence[TaskSpec], config: PilotSkillConfig) -> dict:
        rows = []
        for task in tasks:
            required = str(task.expected_constraints.get("required_text", ""))
            passed = not required or required in task.instruction
            rows.append({"task_id": task.task_id, "passed": passed, "score": 1.0 if passed else 0.0})
        score = sum(row["score"] for row in rows) / len(rows) if rows else 0.0
        return {"task_count": len(rows), "score": score, "rows": rows, "channel": "automated_response_judge"}

    @staticmethod
    def agreement(artifact_report: dict, response_report: dict) -> dict:
        artifact = {row["task_id"]: bool(row["passed"]) for row in artifact_report.get("rows", [])}
        response = {row["task_id"]: bool(row["passed"]) for row in response_report.get("rows", [])}
        common = sorted(set(artifact) & set(response))
        agreements = sum(artifact[item] == response[item] for item in common)
        return {
            "compared": len(common),
            "agreement_rate": agreements / len(common) if common else 0.0,
            "disagreement_count": len(common) - agreements,
            "label": "automated_cross_evaluation",
        }
