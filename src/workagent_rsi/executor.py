from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .contracts import TaskSpec


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

