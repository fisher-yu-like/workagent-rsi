"""Aggregate guarded experiment summaries without turning unavailable into scores."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


# Direct script execution must use this checkout's implementation.
import sys
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'src'))
from workagent_rsi.result_cohorts import analyze_cohorts


def analyze_results(results_root: str | Path) -> dict[str, Any]:
    return analyze_cohorts(Path(results_root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze formal/pilot summaries with fail-closed claim handling")
    parser.add_argument("results_root", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    result = analyze_results(args.results_root)
    output = args.output or args.results_root / "analysis.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
