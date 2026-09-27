from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .contracts import TaskSpec
from .office_capabilities import CapabilityReport, probe_capabilities, verify_artifact_with_com
from .path_safety import validated_task_directory


class MockWorkAgentAdapter:
    """Deterministic adapter used until a real WorkAgent provider is configured."""

    def execute(self, task: TaskSpec, skill_id: str) -> Iterable[dict[str, Any]]:
        yield {"kind": "started", "skill_id": skill_id, "task_id": task.task_id}
        if task.instruction.strip().lower() == "fail":
            yield {"kind": "failure", "message": "controlled failure", "retryable": False}
            return
        if task.instruction.strip().lower() == "timeout":
            yield {"kind": "failure", "message": "controlled timeout", "retryable": True}
            return
        yield {"kind": "artifact", "content": task.instruction, "media_type": "text/plain"}


class LocalOfficeAdapter:
    """Create genuine Office artifacts for local provider qualification."""

    MEDIA_TYPES = {
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "word": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "powerpoint": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    def __init__(self, output_root: str | Path) -> None:
        self.output_root = Path(output_root)

    def execute(self, task: TaskSpec, skill_id: str) -> Iterable[dict[str, Any]]:
        yield {"kind": "started", "skill_id": skill_id, "task_id": task.task_id}
        domain = task.domain.lower()
        if domain not in self.MEDIA_TYPES:
            yield {"kind": "failure", "message": f"unsupported Office domain: {task.domain}", "retryable": False}
            return
        try:
            validated_task_directory(self.output_root, task.task_id)
        except ValueError as exc:
            yield {
                "kind": "failure",
                "message": str(exc),
                "retryable": False,
            }
            return
        marker = str(task.expected_constraints.get("required_text", task.task_id))
        self.output_root.mkdir(parents=True, exist_ok=True)
        if domain == "excel":
            from openpyxl import Workbook

            path = self.output_root / f"{task.task_id}.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Artifact"
            sheet["A1"] = marker
            sheet["A2"] = task.instruction
            workbook.save(path)
        elif domain == "word":
            from docx import Document

            path = self.output_root / f"{task.task_id}.docx"
            document = Document()
            document.add_heading(task.instruction, level=1)
            document.add_paragraph(marker)
            document.save(path)
        else:
            from pptx import Presentation

            path = self.output_root / f"{task.task_id}.pptx"
            presentation = Presentation()
            slide = presentation.slides.add_slide(presentation.slide_layouts[1])
            slide.shapes.title.text = task.instruction
            slide.placeholders[1].text = marker
            presentation.save(path)
        yield {"kind": "artifact", "artifact_path": str(path), "media_type": self.MEDIA_TYPES[domain]}


class UnavailableOfficeAdapter:
    """Fail closed when a requested Office provider is not installed."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        self.message = message

    def execute(self, task: TaskSpec, skill_id: str) -> Iterable[dict[str, Any]]:
        yield {"kind": "started", "skill_id": skill_id, "task_id": task.task_id, "provider": self.provider}
        yield {
            "kind": "unavailable",
            "message": self.message,
            "retryable": False,
            "provider": self.provider,
        }


class ComOfficeAdapter:
    """Generate a genuine package and require Microsoft Office to reopen it."""

    def __init__(
        self,
        output_root: str | Path,
        config: Any,
        capability_report: CapabilityReport | None = None,
        *,
        verifier=verify_artifact_with_com,
    ) -> None:
        self.output_root = Path(output_root)
        self.config = config
        self.capability_report = capability_report
        self.verifier = verifier

    def execute(self, task: TaskSpec, skill_id: str) -> Iterable[dict[str, Any]]:
        from .skill_runtime import SkillConfiguredOfficeAdapter

        domain = task.domain.lower()
        capability_key = f"{domain}_com"
        report = self.capability_report or probe_capabilities()
        yield {"kind": "started", "skill_id": skill_id, "task_id": task.task_id, "provider": "com"}
        if domain not in LocalOfficeAdapter.MEDIA_TYPES:
            yield {"kind": "failure", "message": f"unsupported Office domain: {task.domain}", "retryable": False}
            return
        if not report.is_available(capability_key):
            yield {
                "kind": "unavailable",
                "message": f"COM provider unavailable for {domain}",
                "retryable": False,
                "provider": "com",
                "capability": capability_key,
            }
            return
        delegate = SkillConfiguredOfficeAdapter(self.output_root, self.config)
        for event in delegate.execute(task, skill_id):
            if event["kind"] != "artifact":
                if event["kind"] == "started":
                    continue
                yield event
                continue
            check = self.verifier(event["artifact_path"], domain)
            if not check.get("ok"):
                yield {
                    "kind": "failure",
                    "message": f"COM reopen failed: {check.get('error', 'unknown error')}",
                    "retryable": False,
                    "provider": "com",
                    "com_status": check.get("status"),
                }
                return
            yield {**event, "provider": "com", "com_version": check.get("version")}
