from __future__ import annotations

import json
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
    def __init__(self, evaluator_hash: str) -> None:
        self.evaluator_hash = evaluator_hash

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
