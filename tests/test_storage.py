from pathlib import Path

from workagent_rsi.storage import ArtifactStore, TraceStore


def test_artifact_store_is_content_addressed(tmp_path: Path):
    store = ArtifactStore(tmp_path / "artifacts")
    first = store.put_bytes(b"hello", "text/plain")
    second = store.put_bytes(b"hello", "text/plain")
    assert first.artifact_id == second.artifact_id
    assert Path(first.path).read_bytes() == b"hello"


def test_trace_store_persists_events_and_run_state(tmp_path: Path):
    store = TraceStore(tmp_path / "trace.db")
    store.create_run("run-1", "smoke.echo")
    store.append_event("run-1", "started", {"attempt": 1})
    store.set_state("run-1", "SUCCEEDED")
    assert store.get_state("run-1") == "SUCCEEDED"
    assert store.events("run-1")[0]["kind"] == "started"

