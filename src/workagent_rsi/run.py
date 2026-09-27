"""Run one task with the normal local adapters."""

from __future__ import annotations

from pathlib import Path

from .contracts import TaskSpec
from .evaluator import BasicEvaluator, OfficeArtifactEvaluator
from .executor import ComOfficeAdapter, LocalOfficeAdapter, MockWorkAgentAdapter, UnavailableOfficeAdapter
from .office_capabilities import CapabilityReport
from .orchestrator import Orchestrator
from .skill_runtime import PilotSkillConfig, SkillConfiguredOfficeAdapter
from .store import Store


OFFICE_DOMAINS = {"excel", "word", "powerpoint"}


class Run:
    """Execute a task once and return its checked result."""

    def __init__(
        self,
        root: str | Path,
        *,
        office: bool | None = None,
        execution_provider: str | None = None,
        capability_report: CapabilityReport | None = None,
    ) -> None:
        self.root = Path(root)
        self.store = Store(self.root)
        self.office = office
        self.execution_provider = execution_provider
        self.capability_report = capability_report

    def execute(self, task: TaskSpec, skill_id: str | None = None, *, max_attempts: int = 1) -> dict:
        if isinstance(task, dict):
            task = TaskSpec.model_validate(task)
        use_office = self.office if self.office is not None else task.domain.lower() in OFFICE_DOMAINS
        provider = self.execution_provider or ("local_office" if use_office else "smoke")
        if provider == "smoke":
            adapter = MockWorkAgentAdapter()
            evaluator = BasicEvaluator()
            default_skill = "task.normal"
        elif provider == "local_office":
            adapter = SkillConfiguredOfficeAdapter(
                self.root / "generated",
                PilotSkillConfig(marker_source="required_text"),
            )
            evaluator = OfficeArtifactEvaluator()
            default_skill = "office.normal"
        elif provider == "com":
            adapter = ComOfficeAdapter(
                self.root / "generated",
                PilotSkillConfig(marker_source="required_text"),
                self.capability_report,
            )
            evaluator = OfficeArtifactEvaluator()
            default_skill = "office.com"
        elif provider == "libreoffice":
            adapter = UnavailableOfficeAdapter("libreoffice", "LibreOffice provider is unavailable on this machine")
            evaluator = OfficeArtifactEvaluator()
            default_skill = "office.libreoffice"
        else:
            raise ValueError(f"unknown execution provider: {provider}")
        if provider == "smoke" and use_office and self.execution_provider is None:
            raise ValueError("Office task cannot use smoke provider implicitly")
        if provider != "smoke" and not use_office:
            raise ValueError(f"Office provider {provider} requires an Office task domain")
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


__all__ = ["ComOfficeAdapter", "LocalOfficeAdapter", "MockWorkAgentAdapter", "Run", "UnavailableOfficeAdapter", "run_once"]
