"""Aggregate guarded experiment summaries without turning unavailable into scores."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _summaries(results_root: Path) -> list[dict[str, Any]]:
    summaries = []
    for path in sorted(results_root.rglob("summary.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("mode") in {"pilot", "formal"} and isinstance(payload.get("experiments"), list):
            summaries.append(payload)
    return summaries


def analyze_results(results_root: str | Path) -> dict[str, Any]:
    root = Path(results_root)
    source_summaries = _summaries(root)
    completed: list[dict[str, Any]] = []
    unavailable = 0
    failed = 0
    values: dict[str, list[float]] = defaultdict(list)
    for summary in source_summaries:
        for experiment in summary["experiments"]:
            status = experiment.get("status")
            if status == "completed":
                completed.append(experiment)
                for key, value in experiment.get("metrics", {}).items():
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        values[key].append(float(value))
            elif status in {"unavailable", "timeout"}:
                unavailable += 1
            else:
                failed += 1
    numeric_means = {key: sum(items) / len(items) for key, items in sorted(values.items()) if items}
    formal_summaries = [item for item in source_summaries if item.get("mode") == "formal"]
    claims_allowed = bool(formal_summaries) and unavailable == 0 and failed == 0 and all(
        item.get("dataset_kind") == "external-admitted"
        and item.get("claim_boundary", {}).get("external_benchmark") is True
        for item in formal_summaries
    )
    return {
        "results_root": str(root.resolve()),
        "source_summary_count": len(source_summaries),
        "completed_experiments": len(completed),
        "unavailable_experiments": unavailable,
        "failed_experiments": failed,
        "numeric_means": numeric_means,
        "claims_allowed": claims_allowed,
        "claim_boundary": {
            "unavailable_is_not_a_score": True,
            "pilot_is_not_external_benchmark": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze formal/pilot summaries with fail-closed claim handling")
    parser.add_argument("results_root", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    result = analyze_results(args.results_root)
    output = args.output or args.results_root / "analysis.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
