from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .contracts import TaskSpec
from .evaluator import BasicEvaluator
from .storage import ArtifactStore, TraceStore


class Orchestrator:
    def __init__(self, artifact_store: ArtifactStore, trace_store: TraceStore, adapter, evaluator: BasicEvaluator) -> None:
        self.artifact_store = artifact_store
        self.trace_store = trace_store
        self.adapter = adapter
        self.evaluator = evaluator

    def run(self, task: TaskSpec, skill_id: str, max_attempts: int = 1, *, defer_assessment: bool = False) -> dict:
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
                artifacts = []  # Each execution retry has its own current outputs.
                for event in self.adapter.execute(task, skill_id):
                    self.trace_store.append_event(run_id, event["kind"], {**event, "attempt": attempts})
                    if event["kind"] == "artifact":
                        if "artifact_path" in event:
                            artifact_path = Path(event["artifact_path"])
                            stored = self.artifact_store.put_bytes(
                                artifact_path.read_bytes(), event.get("media_type", "application/octet-stream")
                            )
                            name = event.get("artifact_name") or artifact_path.name
                            artifacts.append(stored.model_copy(update={"name": name}))
                        else:
                            content = event.get("content", b"")
                            if isinstance(content, str):
                                content = content.encode("utf-8")
                            stored = self.artifact_store.put_bytes(
                                content, event.get("media_type", "application/octet-stream")
                            )
                            artifacts.append(stored.model_copy(update={"name": event.get("artifact_name")}))
                    elif event["kind"] in {"failure", "unavailable"}:
                        failure = {
                            "message": event["message"],
                            "retryable": event.get("retryable", False),
                            "attempts": attempts,
                            "status": event.get('status',event["kind"]),
                            "provider": event.get("provider"),
                            'failure_origin':event.get('failure_origin'),
                        }
                        break
                if failure is None or not failure["retryable"] or attempts >= max_attempts:
                    break
                self.trace_store.append_event(run_id, "retrying", {"attempt": attempts, "next_attempt": attempts + 1})
            if failure is not None:
                state = "UNAVAILABLE" if failure.get("status") == "unavailable" else "FAILED"
                self.trace_store.set_state(run_id, state)
                return {"run_id": run_id, "state": state, "artifacts": [a.model_dump(exclude_none=True) for a in artifacts], "failure": failure}
            result = {"run_id":run_id, "state":"EXECUTED", "artifacts":[a.model_dump(exclude_none=True) for a in artifacts]}
            return result if defer_assessment else self.assess_result(task, result)
        except Exception as exc:
            self.trace_store.append_event(run_id, "exception", {"message": str(exc)})
            self.trace_store.set_state(run_id, "FAILED")
            return {"run_id": run_id, "state": "FAILED", "artifacts": [a.model_dump(exclude_none=True) for a in artifacts], "failure": {"message": str(exc), "retryable": False}}

    def assess_result(self, task: TaskSpec, result: dict) -> dict:
        if result.get("failure"):
            return result
        from .contracts import ArtifactRef
        run_id = result["run_id"]
        self.trace_store.set_state(run_id, "EVALUATING")
        try:
            report = self.evaluator.evaluate(task, [ArtifactRef.model_validate(a) for a in result["artifacts"]], run_id)
            state = ("UNAVAILABLE" if report.score is None or report.channel_status.get("assessment") == "incomplete"
                     else "SUCCEEDED" if report.passed else "FAILED")
            evaluation = report.model_dump(mode='json', exclude_none=report.score_semantics!='task-v2')
            evaluation["score"] = report.score
            if not report.report_paths:
                evaluation.pop("report_paths", None)
            self.trace_store.set_state(run_id, state)
            return {**result, "state":state, "evaluation":evaluation}
        except Exception as exc:
            self.trace_store.set_state(run_id, "UNAVAILABLE")
            self.trace_store.append_event(run_id, "assessment_exception", {"type":type(exc).__name__})
            return {**result, "state":"UNAVAILABLE", "failure":{"message":str(exc), "retryable":False,
                    "failure_origin":"assessment_gap"}}

    def resume(self, run_id: str) -> dict:
        return {"run_id": run_id, "state": self.trace_store.get_state(run_id), "events": self.trace_store.events(run_id)}
