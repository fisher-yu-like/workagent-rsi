from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import yaml

from .harness import Harness


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one normal WorkAgent-RSI task")
    results_root = (Path.cwd() / "project_artifacts" / "results").resolve()
    parser.add_argument("task", type=Path)
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=results_root,
        help="folder that contains one directory per run (default: project_artifacts/results)",
    )
    parser.add_argument("--output", type=Path, help="optional exact result.json path for compatibility")
    parser.add_argument(
        "--execution-provider",
        choices=("smoke", "workagent", "local_office", "com", "libreoffice"),
        help="explicit task execution provider; default selects smoke or workagent from the task domain",
    )
    args = parser.parse_args(argv)
    results_dir = args.results_dir.resolve()
    if not results_dir.is_relative_to(results_root):
        parser.error("--results-dir must be inside project_artifacts/results")
    output = args.output.resolve() if args.output is not None else None
    if output is not None:
        if not output.is_relative_to(results_dir) or output.parent == results_dir:
            parser.error("--output must be inside a per-run child directory of --results-dir")
    payload = yaml.safe_load(args.task.read_text(encoding="utf-8"))
    input_base = args.task.resolve().parent
    result = Harness(results_dir, execution_provider=args.execution_provider, input_base=input_base).run(
        payload, result_path=output
    )
    if args.output is None:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["state"] == "SUCCEEDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())

