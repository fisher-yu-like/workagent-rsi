"""Run deterministic Phase 1B cases and write reproducible evidence."""

from __future__ import annotations

import csv
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "project_artifacts" / "phase1_harness" / "results"
LOGS = ROOT / "project_artifacts" / "phase1_harness" / "logs"
REPORTS = ROOT / "project_artifacts" / "phase1_harness" / "reports"

sys.path.insert(0, str(ROOT / "src"))

from workagent_rsi.contracts import TaskSpec
from workagent_rsi.evaluator import BasicEvaluator
from workagent_rsi.executor import MockWorkAgentAdapter
from workagent_rsi.orchestrator import Orchestrator
from workagent_rsi.storage import ArtifactStore, TraceStore


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def run_case(case_id: str, task: TaskSpec) -> dict:
    run_root = RESULTS / case_id
    orchestrator = Orchestrator(
        artifact_store=ArtifactStore(run_root / "artifacts"),
        trace_store=TraceStore(run_root / "trace.db"),
        adapter=MockWorkAgentAdapter(),
        evaluator=BasicEvaluator(),
    )
    started = datetime.now(timezone.utc)
    started_perf = time.perf_counter()
    result = orchestrator.run(task, "smoke.echo", max_attempts=2 if task.instruction == "timeout" else 1)
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
    (run_root / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> int:
    for directory in (RESULTS, LOGS, REPORTS):
        directory.mkdir(parents=True, exist_ok=True)
    cases = {
        "minimal_success": TaskSpec(task_id="smoke-echo", domain="smoke", instruction="hello", expected_constraints={"required_text": "hello"}),
        "complete_success": TaskSpec(task_id="complete-echo", domain="smoke", instruction="monthly report placeholder", expected_constraints={"required_text": "monthly report placeholder"}),
        "controlled_failure": TaskSpec(task_id="controlled-failure", domain="smoke", instruction="fail"),
    }
    results = [run_case(case_id, task) for case_id, task in cases.items()]
    with (RESULTS / "run_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "run_id", "state", "duration_seconds", "git_commit"])
        writer.writeheader()
        writer.writerows({key: result.get(key) for key in writer.fieldnames} for result in results)
    (RESULTS / "run_summary.json").write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    report = [
        "# Phase 1B Mock Pipeline Run Report",
        "",
        f"- Git commit: `{git_commit()}`",
        f"- Python: `{sys.version.split()[0]}`",
        f"- Platform: `{platform.platform()}`",
        f"- Working directory: `{ROOT}`",
        "- Adapter: `MockWorkAgentAdapter` (real external WorkAgent provider is not configured)",
        "",
        "## Results",
        "",
        "| Case | State | Run ID | Duration (s) | Evidence |",
        "|---|---|---|---:|---|",
    ]
    for result in results:
        report.append(f"| {result['case_id']} | {result['state']} | `{result['run_id']}` | {result['duration_seconds']} | `results/{result['case_id']}/result.json` |")
    report.extend(
        [
            "",
            "## Limitations",
            "",
            "This report proves the local Harness contracts, trace persistence, artifact storage, evaluation and failure path using a deterministic mock adapter. It is not evidence that an external WorkAgent provider or real Office application executed successfully.",
        ]
    )
    (REPORTS / "run_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return 0 if all(result["state"] in {"SUCCEEDED", "FAILED"} for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

