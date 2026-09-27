"""Run one task with the normal local adapters."""

from __future__ import annotations

from pathlib import Path

from .contracts import TaskSpec
from .evaluator import BasicEvaluator, OfficeArtifactEvaluator
from .executor import LocalOfficeAdapter, MockWorkAgentAdapter
from .orchestrator import Orchestrator
from .skill_runtime import PilotSkillConfig, SkillConfiguredOfficeAdapter
from .store import Store


OFFICE_DOMAINS = {"excel", "word", "powerpoint"}


class Run:
    """Execute a task once and return its checked result."""

    def __init__(self, root: str | Path, *, office: bool | None = None) -> None:
        self.root = Path(root)
        self.store = Store(self.root)
        self.office = office

    def execute(self, task: TaskSpec, skill_id: str | None = None, *, max_attempts: int = 1) -> dict:
        use_office = self.office if self.office is not None else task.domain.lower() in OFFICE_DOMAINS
        if use_office:
            adapter = SkillConfiguredOfficeAdapter(
                self.root / "generated",
                PilotSkillConfig(marker_source="required_text"),
            )
            evaluator = OfficeArtifactEvaluator()
            default_skill = "office.normal"
        else:
            adapter = MockWorkAgentAdapter()
            evaluator = BasicEvaluator()
            default_skill = "task.normal"
        return Orchestrator(
            artifact_store=self.store.files,
            trace_store=self.store.logs,
            adapter=adapter,
            evaluator=evaluator,
        ).run(task, skill_id or default_skill, max_attempts=max_attempts)

    def resume(self, run_id: str) -> dict:
        """Read the persisted state and trace for a run in this directory."""

        return {
            "run_id": run_id,
            "state": self.store.logs.get_state(run_id),
            "events": self.store.logs.events(run_id),
        }


def run_once(task: TaskSpec, root: str | Path) -> dict:
    """Convenience function for scripts that need one normal run."""

    return Run(root).execute(task)


__all__ = ["LocalOfficeAdapter", "MockWorkAgentAdapter", "Run", "run_once"]
