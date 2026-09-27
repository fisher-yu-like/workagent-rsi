"""Run public pilot tasks through the local real Office artifact adapter."""

from __future__ import annotations

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
RESULT_ROOT = ROOT / "project_artifacts" / "results" / "qualification" / "office"

sys.path.insert(0, str(ROOT / "src"))

from workagent_rsi.data import Task
from workagent_rsi.harness import Harness


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def main() -> int:
    tasks = [json.loads(line) for line in PUBLIC_TASKS.read_text(encoding="utf-8").splitlines() if line.strip()]
    invocation_root = RESULT_ROOT / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    invocation_root.mkdir(parents=True, exist_ok=True)
    rows = []
    started_at = datetime.now(timezone.utc)
    for task_data in tasks:
        task_id = task_data["task_id"]
        task = Task(
            task_id=task_id,
            domain=task_data["domain"],
            instruction=task_data["instruction"],
            input_files=tuple(task_data.get("input_files", [])),
            expected_constraints=task_data.get("expected_constraints", {}),
            risk_level=task_data.get("risk_level", "low"),
            hidden_test=False,
        )
        started_perf = time.perf_counter()
        result = Harness(invocation_root, office=True).run(task, run_id=task_id)
        result.update(
            {
                "task_id": task_id,
                "domain": task_data["domain"],
                "split": task_data["split"],
                "duration_seconds": round(time.perf_counter() - started_perf, 6),
                "git_commit": git_commit(),
                "python": sys.version,
                "platform": platform.platform(),
            }
        )
        Path(result["result_path"]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rows.append(result)
    summary = {
        "run_type": "real_local_office_qualification",
        "qualification_only": True,
        "external_workagent": False,
        "office_artifact_validity": True,
        "dataset_version": json.loads((DATA_ROOT / "provenance.json").read_text(encoding="utf-8"))["dataset_version"],
        "task_count": len(rows),
        "success_count": sum(row["state"] == "SUCCEEDED" for row in rows),
        "failure_count": sum(row["state"] != "SUCCEEDED" for row in rows),
        "mean_score": sum(row.get("evaluation", {}).get("score", 0.0) for row in rows) / len(rows) if rows else 0.0,
        "started_at": started_at.isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "adapter": "LocalOfficeAdapter",
        "evaluator": "OfficeArtifactEvaluator",
        "rows": [{"task_id": row["task_id"], "domain": row["domain"], "split": row["split"], "state": row["state"], "score": row.get("evaluation", {}).get("score", 0.0), "run_id": row["run_id"]} for row in rows],
    }
    (invocation_root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (invocation_root / "qualification_scope.md").write_text(
        "# B0 Office Qualification Scope\n\n"
        "This qualification uses the local Python Office artifact adapter and reopens each generated "
        "DOCX, XLSX or PPTX with its corresponding library. The generated files must also pass the "
        "separate Microsoft Office COM parity script before the provider gate is considered complete. "
        "This is not an external WorkAgent provider run and does not include hidden evaluation.\n",
        encoding="utf-8",
    )
    print(json.dumps({key: summary[key] for key in ("run_type", "task_count", "success_count", "failure_count", "mean_score", "git_commit")}, sort_keys=True))
    return 0 if summary["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
