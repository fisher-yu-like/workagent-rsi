"""Run deterministic evaluator-v2 checks on one fixture per Office domain."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from workagent_rsi.contracts import TaskSpec
from workagent_rsi.evaluator import OfficeArtifactEvaluator
from workagent_rsi.executor import LocalOfficeAdapter
from workagent_rsi.storage import ArtifactStore


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the Office evaluator v2 contract")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "project_artifacts" / "results" / "qualification" / "evaluator-v2",
    )
    args = parser.parse_args(argv)
    invocation_root = args.output_root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    invocation_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    evaluator = OfficeArtifactEvaluator()
    with tempfile.TemporaryDirectory(prefix="workagent-evaluator-v2-") as temp_dir:
        root = Path(temp_dir)
        for domain in ("excel", "word", "powerpoint"):
            marker = f"EVALUATOR-V2-{domain.upper()}"
            task = TaskSpec(
                task_id=f"evaluator-v2-{domain}",
                domain=domain,
                instruction=f"Create a {domain} artifact containing {marker}",
                expected_constraints={"required_text": marker},
            )
            events = list(LocalOfficeAdapter(root / domain / "generated").execute(task, "evaluator-v2"))
            final = events[-1]
            if final.get("kind") != "artifact":
                rows.append({"domain": domain, "passed": False, "failure": final})
                continue
            store = ArtifactStore(root / domain / "artifacts")
            ref = store.put_file(final["artifact_path"], final["media_type"])
            report = evaluator.evaluate(task, [ref], f"evaluator-v2-{domain}")
            rows.append(
                {
                    "domain": domain,
                    "passed": report.passed,
                    "score": report.score,
                    "dimensions": report.dimensions,
                    "critical_failures": report.critical_failures,
                    "warnings": report.warnings,
                    "channel_status": report.channel_status,
                }
            )

    payload = {
        "status": "passed" if all(bool(row.get("passed")) for row in rows) else "failed",
        "stage": 2,
        "evaluator": evaluator.VERSION,
        "evaluator_hash": evaluator.evaluator_hash(),
        "git_commit": git_commit(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
        "policy": "pixel/rendering unavailable is recorded and never converted into a score",
    }
    (invocation_root / "validation.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "result_dir": str(invocation_root), "evaluator_hash": payload["evaluator_hash"]}, sort_keys=True))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
