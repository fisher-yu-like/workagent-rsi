from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import yaml

from .harness import Harness


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one normal WorkAgent-RSI task")
    parser.add_argument("task", type=Path)
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("project_artifacts") / "results",
        help="folder that contains one directory per run (default: project_artifacts/results)",
    )
    parser.add_argument("--output", type=Path, help="optional exact result.json path for compatibility")
    parser.add_argument(
        "--execution-provider",
        choices=("smoke", "local_office", "com", "libreoffice"),
        help="explicit task execution provider; default selects smoke or local_office from the task domain",
    )
    args = parser.parse_args(argv)
    payload = yaml.safe_load(args.task.read_text(encoding="utf-8"))
    result = Harness(args.results_dir, execution_provider=args.execution_provider).run(payload, result_path=args.output)
    if args.output is None:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["state"] == "SUCCEEDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())

