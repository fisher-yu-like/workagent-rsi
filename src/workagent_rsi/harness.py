"""The one public entry point for a normal WorkAgent-RSI run."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .contracts import TaskSpec
from .run import Run


class Harness:
    """Run one task and keep all evidence in one result directory.

    The default path is ``project_artifacts/results``. A normal Office run uses
    the required task text, so a first run measures the task as written instead
    of starting from a deliberately broken skill.
    """

    def __init__(self, results_dir: str | Path = "project_artifacts/results", *, office: bool | None = None) -> None:
        self.results_dir = Path(results_dir)
        self.office = office

    def run(
        self,
        task: TaskSpec | dict,
        *,
        run_id: str | None = None,
        result_path: str | Path | None = None,
        max_attempts: int = 1,
    ) -> dict:
        task = task if isinstance(task, TaskSpec) else TaskSpec.model_validate(task)
        root, output = self._paths(task, run_id=run_id, result_path=result_path)
        if output.exists():
            raise FileExistsError(output)
        root.mkdir(parents=True, exist_ok=True)
        (root / "task.json").write_text(
            json.dumps(task.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        result = Run(root, office=self.office).execute(task, max_attempts=max_attempts)
        result["result_path"] = str(output.resolve())
        result["result_dir"] = str(root.resolve())
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result

    def resume(self, result_dir: str | Path, *, run_id: str | None = None) -> dict:
        """Return the persisted state and trace for a completed or failed run."""

        root = Path(result_dir)
        result_file = root / "result.json"
        if run_id is None:
            if not result_file.exists():
                raise FileNotFoundError(result_file)
            run_id = json.loads(result_file.read_text(encoding="utf-8")).get("run_id")
        if not run_id:
            raise ValueError("result.json does not contain a run_id")
        return Run(root, office=self.office).resume(run_id)

    def _paths(
        self,
        task: TaskSpec,
        *,
        run_id: str | None,
        result_path: str | Path | None,
    ) -> tuple[Path, Path]:
        if result_path is not None:
            output = Path(result_path)
            return output.parent, output
        self.results_dir.mkdir(parents=True, exist_ok=True)
        identifier = run_id or self._run_id(task)
        root = self.results_dir / identifier
        return root, root / "result.json"

    @staticmethod
    def _run_id(task: TaskSpec) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_task = re.sub(r"[^A-Za-z0-9_-]+", "-", task.task_id).strip("-") or "task"
        return f"{stamp}-{safe_task}-{uuid4().hex[:8]}"


__all__ = ["Harness"]
