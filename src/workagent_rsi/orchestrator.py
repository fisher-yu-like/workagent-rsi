from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .contracts import TaskSpec
from .evaluator import BasicEvaluator
from .executor import MockWorkAgentAdapter
from .storage import ArtifactStore, TraceStore


class Orchestrator:
    def __init__(self, artifact_store: ArtifactStore, trace_store: TraceStore, adapter: MockWorkAgentAdapter, evaluator: BasicEvaluator) -> None:
        self.artifact_store = artifact_store
        self.trace_store = trace_store
        self.adapter = adapter
        self.evaluator = evaluator

    def run(self, task: TaskSpec, skill_id: str, max_attempts: int = 1) -> dict:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        run_id = f"run-{uuid4().hex[:12]}"
        started_at = datetime.now(timezone.utc).isoformat()
        self.trace_store.create_run(run_id, task.task_id)
        self.trace_store.append_event(run_id, "run_started", {"skill_id": skill_id, "started_at": started_at})
        self.trace_store.set_state(run_id, "RUNNING")
        artifacts = []
        failure = None
        attempts = 0
        try:
            while attempts < max_attempts:
                attempts += 1
                failure = None
                for event in self.adapter.execute(task, skill_id):
                    self.trace_store.append_event(run_id, event["kind"], {**event, "attempt": attempts})
                    if event["kind"] == "artifact":
                        if "artifact_path" in event:
                            artifact_path = Path(event["artifact_path"])
                            artifacts.append(self.artifact_store.put_bytes(artifact_path.read_bytes(), event.get("media_type", "application/octet-stream")))
                        else:
                            content = event.get("content", b"")
                            if isinstance(content, str):
                                content = content.encode("utf-8")
                            artifacts.append(self.artifact_store.put_bytes(content, event.get("media_type", "application/octet-stream")))
                    elif event["kind"] == "failure":
                        failure = {"message": event["message"], "retryable": event.get("retryable", False), "attempts": attempts}
                        break
                if failure is None or not failure["retryable"] or attempts >= max_attempts:
                    break
                self.trace_store.append_event(run_id, "retrying", {"attempt": attempts, "next_attempt": attempts + 1})
            if failure is not None:
                self.trace_store.set_state(run_id, "FAILED")
                return {"run_id": run_id, "state": "FAILED", "artifacts": [a.model_dump() for a in artifacts], "failure": failure}
            self.trace_store.set_state(run_id, "EVALUATING")
            report = self.evaluator.evaluate(task, artifacts, run_id)
            state = "SUCCEEDED" if report.passed else "FAILED"
            self.trace_store.set_state(run_id, state)
            return {"run_id": run_id, "state": state, "artifacts": [a.model_dump() for a in artifacts], "evaluation": report.model_dump()}
        except Exception as exc:
            self.trace_store.append_event(run_id, "exception", {"message": str(exc)})
            self.trace_store.set_state(run_id, "FAILED")
            return {"run_id": run_id, "state": "FAILED", "artifacts": [a.model_dump() for a in artifacts], "failure": {"message": str(exc), "retryable": False}}

    def resume(self, run_id: str) -> dict:
        return {"run_id": run_id, "state": self.trace_store.get_state(run_id), "events": self.trace_store.events(run_id)}
