"""Frozen, real-artifact evaluation for WorkAgent RSI."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Sequence

from .contracts import TaskSpec
from .evaluator import OfficeArtifactEvaluator
from .harness import Harness
from .hashing import canonical_json_hash
from .path_safety import validated_task_directory
from .rsi_contracts import EvaluationContract
from .workagent_provider import WorkAgentConfig, WorkAgentSkill


class WorkAgentFrozenEvaluator:
    def __init__(
        self,
        evaluator_hash: str,
        *,
        workagent_config: WorkAgentConfig | None = None,
        input_base: str | Path | None = None,
    ) -> None:
        self.evaluator_hash = evaluator_hash
        self.workagent_config = workagent_config or WorkAgentConfig()
        self.input_base = Path(input_base) if input_base is not None else Path.cwd()

    def evaluate_split(
        self,
        tasks: Sequence[TaskSpec],
        split_name: str,
        config: WorkAgentSkill,
        contract: EvaluationContract,
        result_root: str | Path,
        *,
        reveal_per_task: bool = False,
    ) -> dict:
        split_hash = canonical_json_hash([task.model_dump(mode="json") for task in tasks])
        if contract.split_hashes.get(split_name) != split_hash:
            raise ValueError("split hash does not match frozen evaluation contract")
        live_evaluator_hash = OfficeArtifactEvaluator.evaluator_hash()
        if contract.evaluator_hash != self.evaluator_hash or self.evaluator_hash != live_evaluator_hash:
            raise ValueError("evaluator hash does not match frozen evaluation contract")
        root = Path(result_root)
        root.mkdir(parents=True, exist_ok=True)
        rows: list[dict] = []
        completed_seconds = 0.0
        for task in tasks:
            task_root = validated_task_directory(root, task.task_id)
            harness = Harness(
                task_root,
                execution_provider="workagent",
                workagent_config=self.workagent_config,
                agent_instructions=config.instructions,
                input_base=self.input_base,
            )
            started = time.perf_counter()
            result = harness.run(task, run_id="run")
            elapsed = time.perf_counter() - started
            evaluation = result.get("evaluation")
            raw_score = evaluation.get("score") if isinstance(evaluation, dict) else None
            valid_score = isinstance(raw_score, (int, float)) and not isinstance(raw_score, bool) and math.isfinite(raw_score)
            terminal = result.get("state") in {"SUCCEEDED", "FAILED"} and valid_score
            row = {
                "task_id": task.task_id,
                "domain": task.domain,
                "state": result.get("state"),
                "result_dir": result["result_dir"],
            }
            if terminal:
                row.update(
                    passed=bool(evaluation.get("passed")),
                    score=float(raw_score),
                    critical_failures=evaluation.get("critical_failures", []),
                    wall_time_seconds=round(elapsed, 6),
                )
                completed_seconds += elapsed
            else:
                row["status"] = "incomplete"
                row["failure"] = result.get("failure") or "missing or invalid terminal evaluation score"
            rows.append(row)
        complete = len(rows) == len(tasks) and bool(tasks) and all("score" in row for row in rows)
        full = {
            "split": split_name,
            "status": "completed" if complete else "incomplete",
            "task_count": len(tasks),
            "completed_count": sum("score" in row for row in rows),
            "success_count": sum(bool(row.get("passed")) for row in rows),
            "split_hash": split_hash,
            "evaluator_hash": live_evaluator_hash,
            "rows": rows,
        }
        if full["completed_count"]:
            full["completed_wall_time_seconds"] = round(completed_seconds, 6)
        if complete:
            full["score"] = sum(row["score"] for row in rows) / len(rows)
        (root / "evaluation_full.json").write_text(json.dumps(full, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        public = {key: value for key, value in full.items() if key != "rows"}
        if split_name == "develop" and reveal_per_task:
            public["rows"] = rows
        (root / "evaluation_public.json").write_text(json.dumps(public, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return public
