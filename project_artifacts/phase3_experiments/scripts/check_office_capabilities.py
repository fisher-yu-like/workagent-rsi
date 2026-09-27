"""Record explicit Office/provider capability evidence below the unified results root."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from workagent_rsi.office_capabilities import probe_capabilities


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Office and provider capabilities")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "project_artifacts" / "results" / "qualification" / "capabilities",
    )
    args = parser.parse_args(argv)
    invocation = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = args.output_root / invocation
    root.mkdir(parents=True, exist_ok=True)
    report = probe_capabilities()
    payload = {
        "git_commit": git_commit(),
        "working_directory": str(ROOT),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "report": report.model_dump(mode="json"),
    }
    (root / "capability_report.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        name: item.status
        for name, item in report.capabilities.items()
        if name in {"word_com", "excel_com", "powerpoint_com", "libreoffice", "external_workagent"}
    }
    print(json.dumps({"status": "completed", "result_dir": str(root), "capabilities": summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
