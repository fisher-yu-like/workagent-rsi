"""Run deterministic Phase 1B cases and write reproducible evidence."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "project_artifacts" / "results" / "phase1"

sys.path.insert(0, str(ROOT / "src"))

from workagent_rsi.harness import Harness
from workagent_rsi.data import Task


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def run_case(case_id: str, task: Task, result_root: Path) -> dict:
    started = datetime.now(timezone.utc)
    started_perf = time.perf_counter()
    result = Harness(result_root, office=False).run(task, run_id=case_id)
    ended = datetime.now(timezone.utc)
    result.update(
        {
            "case_id": case_id,
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "duration_seconds": round(time.perf_counter() - started_perf, 6),
            "git_commit": git_commit(),
            "python": sys.version,
            "platform": platform.platform(),
            "workdir": str(ROOT),
        }
    )
    Path(result["result_path"]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    invocation_root = RESULTS / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    reports = invocation_root / "reports"
    for directory in (invocation_root, reports):
        directory.mkdir(parents=True, exist_ok=True)
    cases = {
        "minimal_success": Task(task_id="smoke-echo", domain="smoke", instruction="hello", expected_constraints={"required_text": "hello"}),
        "complete_success": Task(task_id="complete-echo", domain="smoke", instruction="monthly report placeholder", expected_constraints={"required_text": "monthly report placeholder"}),
    }
    results = [run_case(case_id, task, invocation_root) for case_id, task in cases.items()]
    (invocation_root / "run_summary.json").write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    report = [
        "# Phase 1B Mock Pipeline Run Report",
        "",
        f"- Git commit: `{git_commit()}`",
        f"- Python: `{sys.version.split()[0]}`",
        f"- Platform: `{platform.platform()}`",
        f"- Working directory: `{ROOT}`",
        "- Adapter: `Harness` with the deterministic smoke runner",
        "",
        "## Results",
        "",
        "| Case | State | Run ID | Duration (s) | Evidence |",
        "|---|---|---|---:|---|",
    ]
    for result in results:
        report.append(f"| {result['case_id']} | {result['state']} | `{result['run_id']}` | {result['duration_seconds']} | `{result['result_path']}` |")
    report.extend(["", "This normal run keeps both examples on the success path. Failure handling remains covered by unit tests and can be investigated separately."])
    (reports / "run_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return 0 if all(result["state"] == "SUCCEEDED" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

