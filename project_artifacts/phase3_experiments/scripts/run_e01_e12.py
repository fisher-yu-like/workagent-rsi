from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from workagent_rsi.candidate_provider import CodexCandidateProvider, DeterministicCandidateProvider
from workagent_rsi.experiment_runner import ExperimentRunner


def codex_version() -> str:
    try:
        return subprocess.check_output(["codex", "--version"], text=True, stderr=subprocess.STDOUT).strip()
    except Exception:
        return "unavailable"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run WorkAgent-RSI E01-E12 pilot experiments")
    parser.add_argument("--provider", choices=("codex", "deterministic"), default="codex")
    parser.add_argument("--experiments", default=",".join(f"E{index:02d}" for index in range(1, 13)))
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "project_artifacts" / "phase3_experiments" / "results" / "e01_e12",
    )
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()

    schema = ROOT / "project_artifacts" / "phase3_experiments" / "provider" / "candidate_patch.schema.json"
    if args.provider == "codex":
        provider = CodexCandidateProvider(
            schema_path=schema,
            provider_version=codex_version(),
            timeout_seconds=args.timeout_seconds,
        )
    else:
        provider = DeterministicCandidateProvider()
    runner = ExperimentRunner(ROOT / "project_artifacts" / "phase3_experiments" / "data", ROOT)
    prefix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    results = []
    for experiment_id in [item.strip() for item in args.experiments.split(",") if item.strip()]:
        result = runner.run(
            experiment_id,
            provider,
            args.output_root,
            invocation_id=f"{prefix}-{args.provider.lower()}-{experiment_id.lower()}",
        )
        results.append(result.model_dump(mode="json"))
        print(json.dumps(results[-1], sort_keys=True))
    failed = [item for item in results if item["status"] in {"failed", "blocked"}]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
