from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import yaml

from .contracts import TaskSpec
from .evaluator import BasicEvaluator
from .executor import MockWorkAgentAdapter
from .orchestrator import Orchestrator
from .storage import ArtifactStore, TraceStore


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the WorkAgent-RSI local mock pipeline")
    parser.add_argument("task", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = yaml.safe_load(args.task.read_text(encoding="utf-8"))
    task = TaskSpec.model_validate(payload)
    root = args.output.parent / ".run-data"
    result = Orchestrator(ArtifactStore(root / "artifacts"), TraceStore(root / "trace.db"), MockWorkAgentAdapter(), BasicEvaluator()).run(task, "smoke.echo")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return 0 if result["state"] == "SUCCEEDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())

