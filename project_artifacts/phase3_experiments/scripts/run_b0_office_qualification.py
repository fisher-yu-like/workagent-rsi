"""Run public pilot tasks through the local real Office artifact adapter."""

from __future__ import annotations

import json
import argparse
import hashlib
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = ROOT / "project_artifacts" / "phase3_experiments" / "data"
PUBLIC_TASKS = DATA_ROOT / "processed" / "public_tasks.jsonl"
RESULT_ROOT = ROOT / "project_artifacts" / "results" / "qualification"

sys.path.insert(0, str(ROOT / "src"))

from workagent_rsi.data import Task
from workagent_rsi.harness import Harness
from workagent_rsi.office_capabilities import probe_capabilities


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def git_state() -> dict[str, object]:
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    diff = subprocess.check_output(["git", "diff", "--binary"], cwd=ROOT)
    return {
        "git_worktree_dirty": bool(status.strip()),
        "git_diff_sha256": hashlib.sha256(diff).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run public Office qualification through an explicit provider")
    parser.add_argument("--provider", choices=("local_office", "com"), default="local_office")
    args = parser.parse_args(argv)
    tasks = [json.loads(line) for line in PUBLIC_TASKS.read_text(encoding="utf-8").splitlines() if line.strip()]
    result_group = "real-office" if args.provider == "com" else "office"
    invocation_root = RESULT_ROOT / result_group / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    invocation_root.mkdir(parents=True, exist_ok=True)
    capability_report = probe_capabilities() if args.provider == "com" else None
    repository_state = git_state()
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
        result = Harness(
            invocation_root,
            office=True,
            execution_provider=args.provider,
            capability_report=capability_report,
        ).run(task, run_id=task_id)
        result.update(
            {
                "task_id": task_id,
                "domain": task_data["domain"],
                "split": task_data["split"],
                "duration_seconds": round(time.perf_counter() - started_perf, 6),
                "git_commit": git_commit(),
                **repository_state,
                "python": sys.version,
                "platform": platform.platform(),
            }
        )
        Path(result["result_path"]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rows.append(result)
    summary = {
        "run_type": "real_office_provider_qualification",
        "provider": args.provider,
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
        **repository_state,
        "python": sys.version,
        "platform": platform.platform(),
        "adapter": "ComOfficeAdapter" if args.provider == "com" else "SkillConfiguredOfficeAdapter",
        "evaluator": "OfficeArtifactEvaluator",
        "rows": [{"task_id": row["task_id"], "domain": row["domain"], "split": row["split"], "state": row["state"], "score": row.get("evaluation", {}).get("score", 0.0), "run_id": row["run_id"]} for row in rows],
    }
    (invocation_root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (invocation_root / "qualification_scope.md").write_text(
        "# Office Provider Qualification Scope\n\n"
        f"This qualification uses the explicit `{args.provider}` provider. It generates genuine DOCX, "
        "XLSX or PPTX artifacts and checks them with the repository evaluator. The COM provider also "
        "reopens each artifact through Microsoft Office 16.0 before the artifact is accepted. This is "
        "not an external WorkAgent provider run and does not include hidden evaluation.\n",
        encoding="utf-8",
    )
    print(json.dumps({key: summary[key] for key in ("run_type", "task_count", "success_count", "failure_count", "mean_score", "git_commit")}, sort_keys=True))
    return 0 if summary["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
