"""T03 bundle portability, integrity, exclusivity and safe metadata."""

import json
from pathlib import Path
import shutil

import pytest

from workagent_rsi.evidence_bundle import write_evidence_bundle, verify_evidence_bundle


def record(source):
    return {
        "run_id": "authored-offline-test", "git_commit": "a" * 40,
        "command": ["explicit-python", "-m", "pytest"], "exit_code": 0,
        "started_at": "2026-10-21T00:00:00+00:00", "ended_at": "2026-10-21T00:00:01+00:00",
        "identities": {"code": "b" * 64, "input": "c" * 64, "skill": "d" * 64, "spec": "e" * 64},
        "model": {"provider": "stub", "model": "offline-test", "protocol": "chat_completions", "endpoint": "https://review.invalid/v1"},
        "capabilities": [{"role": "executor", "chat_completions": "available"}, {"role": "judge"}],
        "files": {"stdout": source},
    }


def test_bundle_moves_without_absolute_reference_dependencies(tmp_path):
    source = tmp_path / "stdout.txt"
    source.write_text("independently known output\n", encoding="utf-8")
    manifest = write_evidence_bundle(tmp_path / "original", record(source))
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["files"]["stdout"]["path"] == "files/stdout"
    assert payload["usage"]["tokens"] is None
    assert payload["capabilities"][1]["responses"] == "not_probed"
    moved = tmp_path / "moved"
    shutil.move(str(manifest.parent), moved)
    source.unlink()
    resolved = verify_evidence_bundle(moved / "manifest.json")
    assert resolved["stdout"].read_text(encoding="utf-8") == "independently known output\n"


def test_bundle_never_overwrites_and_detects_tampered_evidence(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("original", encoding="utf-8")
    manifest = write_evidence_bundle(tmp_path / "bundle", record(source))
    before = manifest.read_bytes()
    with pytest.raises(FileExistsError):
        write_evidence_bundle(manifest.parent, record(source))
    assert manifest.read_bytes() == before
    (manifest.parent / "files/stdout").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        verify_evidence_bundle(manifest)


@pytest.mark.parametrize("secret", [
    {"Authorization": "Bearer dummy-only"}, {"api_key": "dummy-only"},
    {"nested": {"password": "dummy-only"}},
])
def test_sensitive_metadata_is_rejected_before_creating_bundle(tmp_path, secret):
    source = tmp_path / "source.txt"
    source.write_text("safe", encoding="utf-8")
    payload = record(source)
    payload["configuration"] = secret
    with pytest.raises(ValueError):
        write_evidence_bundle(tmp_path / "bundle", payload)
    assert not (tmp_path / "bundle").exists()


def test_endpoint_credentials_and_traversal_are_rejected(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("safe", encoding="utf-8")
    payload = record(source)
    payload["model"]["endpoint"] = "https://user:dummy@review.invalid/v1"
    with pytest.raises(ValueError):
        write_evidence_bundle(tmp_path / "bad-endpoint", payload)
    payload = record(source)
    payload["files"] = {"../escape": source}
    with pytest.raises(ValueError):
        write_evidence_bundle(tmp_path / "bad-path", payload)
    assert not (tmp_path / "escape").exists()


def test_resolver_rejects_a_manifest_reference_outside_bundle(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("safe", encoding="utf-8")
    manifest = write_evidence_bundle(tmp_path / "bundle", record(source))
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["files"]["stdout"]["path"] = "../source.txt"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        verify_evidence_bundle(manifest)


def test_bundle_rejects_path_collisions_and_invalid_timestamps_before_output(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("safe", encoding="utf-8")
    payload = record(source)
    payload["files"] = {"a": source, "a/nested": source}
    with pytest.raises(ValueError):
        write_evidence_bundle(tmp_path / "collision", payload)
    assert not (tmp_path / "collision").exists()
    payload = record(source)
    payload["ended_at"] = "2026-10-20T00:00:00+00:00"
    with pytest.raises(ValueError):
        write_evidence_bundle(tmp_path / "reversed", payload)
    assert not (tmp_path / "reversed").exists()
