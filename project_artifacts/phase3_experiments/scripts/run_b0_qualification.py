"""Run the public pilot through the local mock Harness for qualification only."""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = ROOT / "project_artifacts" / "phase3_experiments" / "data"
PUBLIC_TASKS = DATA_ROOT / "processed" / "public_tasks.jsonl"
RESULT_ROOT = ROOT / "project_artifacts" / "phase3_experiments" / "results" / "b0_qualification"

sys.path.insert(0, str(ROOT / "src"))

from workagent_rsi.contracts import TaskSpec
from workagent_rsi.evaluator import BasicEvaluator
from workagent_rsi.executor import MockWorkAgentAdapter
from workagent_rsi.orchestrator import Orchestrator
from workagent_rsi.path_safety import validated_task_directory
from workagent_rsi.storage import ArtifactStore, TraceStore


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    tasks = [json.loads(line) for line in PUBLIC_TASKS.read_text(encoding="utf-8").splitlines() if line.strip()]
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc)
    rows: list[dict] = []
    for task_data in tasks:
        task_id = task_data["task_id"]
        run_root = validated_task_directory(RESULT_ROOT, task_id)
        orchestrator = Orchestrator(
            artifact_store=ArtifactStore(run_root / "artifacts"),
            trace_store=TraceStore(run_root / "trace.db"),
            adapter=MockWorkAgentAdapter(),
            evaluator=BasicEvaluator(),
        )
        started_perf = time.perf_counter()
        task = TaskSpec(
            task_id=task_data["task_id"],
            domain=task_data["domain"],
            instruction=task_data["instruction"],
            input_files=tuple(task_data.get("input_files", [])),
            expected_constraints=task_data.get("expected_constraints", {}),
            risk_level=task_data.get("risk_level", "low"),
            hidden_test=task_data.get("hidden_test", False),
        )
        result = orchestrator.run(task, "b0.fixed.mock", max_attempts=1)
        result.update(
            {
                "task_id": task_id,
                "domain": task_data["domain"],
                "split": task_data["split"],
                "duration_seconds": round(time.perf_counter() - started_perf, 6),
                "git_commit": git_commit(),
                "python": sys.version,
                "platform": platform.platform(),
                "workdir": str(ROOT),
            }
        )
        (run_root / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rows.append(result)

    summary = {
        "run_type": "mock_harness_qualification",
        "qualification_only": True,
        "external_workagent": False,
        "office_artifact_validity": False,
        "dataset_version": json.loads((DATA_ROOT / "provenance.json").read_text(encoding="utf-8"))["dataset_version"],
        "dataset_public_sha256": sha256(PUBLIC_TASKS),
        "task_count": len(rows),
        "success_count": sum(row["state"] == "SUCCEEDED" for row in rows),
        "failure_count": sum(row["state"] != "SUCCEEDED" for row in rows),
        "mean_score": sum(row.get("evaluation", {}).get("score", 0.0) for row in rows) / len(rows) if rows else 0.0,
        "started_at": started_at.isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "evaluator": "BasicEvaluator",
        "adapter": "MockWorkAgentAdapter",
        "rows": [{"task_id": row["task_id"], "split": row["split"], "state": row["state"], "score": row.get("evaluation", {}).get("score", 0.0), "run_id": row["run_id"]} for row in rows],
    }
    (RESULT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (RESULT_ROOT / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["task_id", "split", "state", "score", "run_id"])
        writer.writeheader()
        writer.writerows(summary["rows"])
    (RESULT_ROOT / "qualification_scope.md").write_text(
        "# B0 Qualification Scope\n\n"
        "This is a real execution of the local Harness over the public project-generated task set. "
        "The MockWorkAgentAdapter emits text and BasicEvaluator checks a required marker. The result "
        "is evidence for trace/evaluator plumbing only, not Office artifact correctness, external "
        "WorkAgent performance, or an external benchmark score.\n",
        encoding="utf-8",
    )
    print(json.dumps({key: summary[key] for key in ("run_type", "task_count", "success_count", "failure_count", "mean_score", "git_commit")}, sort_keys=True))
    return 0 if summary["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
