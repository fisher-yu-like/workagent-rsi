import json
import subprocess
from pathlib import Path

import pytest
from docx import Document
from openpyxl import Workbook
from pydantic import ValidationError

from workagent_rsi.contracts import TaskSpec
from workagent_rsi.hashing import canonical_json_hash, sha256_file
from workagent_rsi.workagent_office import build_task_prompt, copy_task_inputs, validate_deliverables, verify_task_input_hashes
from workagent_rsi.workagent_provider import (
    AgentResponse,
    CodexOfficeProvider,
    ProviderOutcome,
    WorkAgentConfig,
    build_agent_response_schema,
)


def test_workagent_config_has_bounded_local_defaults():
    config = WorkAgentConfig()
    assert (config.model, config.executable, config.timeout_seconds, config.max_output_files) == (
        "qwen2.5:7b", "codex", 600, 8
    )
    assert config.max_artifact_bytes == 100 * 1024 * 1024
    assert config.verify_com is True


@pytest.mark.parametrize("field", ["timeout_seconds", "max_output_files", "max_artifact_bytes"])
def test_workagent_config_rejects_nonpositive_limits(field):
    with pytest.raises(ValidationError):
        WorkAgentConfig.model_validate({field: 0})


def test_agent_response_rejects_unknown_status_and_absolute_paths():
    with pytest.raises(ValidationError):
        AgentResponse.model_validate({"status": "maybe", "deliverables": [], "summary": "x", "input_files_used": []})
    for path in ("/root/report.xlsx", "C:/report.xlsx", "//server/share/report.xlsx"):
        with pytest.raises(ValidationError):
            AgentResponse(status="completed", deliverables=[path], summary="x", input_files_used=[])


@pytest.mark.parametrize("path", ["../report.xlsx", "outputs/../report.xlsx", "outputs//report.xlsx", "outputs/", "", r"outputs\report.xlsx", "./report.xlsx"])
@pytest.mark.parametrize("field", ["deliverables", "input_files_used"])
def test_agent_response_rejects_unsafe_relative_paths(path, field):
    payload = {"status": "completed", "deliverables": [], "summary": "x", "input_files_used": []}
    payload[field] = [path]
    with pytest.raises(ValidationError):
        AgentResponse.model_validate(payload)


def test_agent_response_accepts_posix_relative_paths_and_forbids_extras():
    response = AgentResponse(
        status="completed",
        deliverables=["outputs/report.xlsx"],
        summary="Created report",
        input_files_used=["inputs/0001-source.xlsx"],
    )
    assert response.deliverables == ["outputs/report.xlsx"]
    with pytest.raises(ValidationError):
        AgentResponse.model_validate({**response.model_dump(), "unexpected": True})


def test_agent_response_schema_resource_matches_builder():
    resource = Path(__file__).resolve().parents[1] / "src/workagent_rsi/schemas/agent_response.schema.json"
    schema = json.loads(resource.read_text(encoding="utf-8"))
    assert schema == build_agent_response_schema()
    assert set(schema["required"]) == {"status", "deliverables", "summary", "input_files_used"}
    assert schema["additionalProperties"] is False


def test_provider_outcome_rejects_unknown_status():
    with pytest.raises(ValidationError):
        ProviderOutcome(status="maybe")


def test_provider_uses_ollama_ephemeral_workspace_write_and_schema(tmp_path: Path):
    provider = CodexOfficeProvider(WorkAgentConfig())
    response_path = tmp_path / "agent_response.json"
    command = provider.command(tmp_path, response_path, provider.schema_path)

    assert command[:2] == ["codex", "exec"]
    assert command[command.index("--sandbox") + 1] == "workspace-write"
    assert command[command.index("--local-provider") + 1] == "ollama"
    assert command[command.index("--model") + 1] == "qwen2.5:7b"
    assert command[command.index("--output-schema") + 1] == str(provider.schema_path)
    assert command[command.index("--output-last-message") + 1] == str(response_path)
    assert command[command.index("--cd") + 1] == str(tmp_path)
    assert "--ignore-user-config" in command
    assert "--oss" in command
    assert "--json" in command
    assert "--ephemeral" in command
    assert command[-1] == "-"
    assert "--dangerously-bypass-approvals-and-sandbox" not in command


def test_provider_runs_prompt_on_stdin_and_persists_success_evidence(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "input.txt").write_text("source", encoding="utf-8")
    records = tmp_path / "records"
    response = {"status": "completed", "deliverables": ["outputs/report.docx"], "summary": "Created report", "input_files_used": ["inputs/source.txt"]}
    observed = {}

    def fake_run(command, **kwargs):
        observed.update(command=command, **kwargs)
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(response), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout='{"type":"done"}\n', stderr="notice\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    outcome = CodexOfficeProvider(WorkAgentConfig()).run("make a report", workspace, records)

    assert outcome.status == "completed"
    assert outcome.response == AgentResponse.model_validate(response)
    assert outcome.record is not None
    assert outcome.record.model_identity == "ollama:qwen2.5:7b"
    assert outcome.record.prompt_hash == canonical_json_hash({"prompt": "make a report"})
    assert outcome.record.workspace_hash == canonical_json_hash({"input.txt": sha256_file(workspace / "input.txt")})
    assert outcome.record.exit_code == 0
    assert outcome.record.started_at <= outcome.record.ended_at
    response_path = Path(observed["command"][observed["command"].index("--output-last-message") + 1])
    assert outcome.record.output_ref == sha256_file(response_path)
    assert observed["input"] == "make a report"
    assert observed["capture_output"] is True
    assert observed["text"] is True
    assert observed["timeout"] == 600
    assert observed["command"][-1] == "-"
    assert (records / "prompt.md").read_text(encoding="utf-8") == "make a report"
    assert (records / "provider.stdout.jsonl").read_text(encoding="utf-8") == '{"type":"done"}\n'
    assert (records / "provider.stderr.txt").read_text(encoding="utf-8") == "notice\n"
    assert response_path.parent == workspace
    assert json.loads(response_path.read_text(encoding="utf-8")) == response
    assert json.loads((workspace / "agent_response.json").read_text(encoding="utf-8")) == response
    assert json.loads((records / "agent_response.json").read_text(encoding="utf-8")) == response
    assert json.loads((records / "command.json").read_text(encoding="utf-8")) == observed["command"]
    assert json.loads((records / "provider_record.json").read_text(encoding="utf-8")) == outcome.record.model_dump(mode="json")


def test_provider_timeout_preserves_partial_output(monkeypatch, tmp_path: Path):
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=b"partial stdout", stderr=b"partial stderr")

    monkeypatch.setattr(subprocess, "run", fake_run)
    records = tmp_path / "records"
    outcome = CodexOfficeProvider(WorkAgentConfig()).run("prompt", tmp_path, records)

    assert outcome.status == "timeout"
    assert outcome.response is None
    assert outcome.record is not None
    assert outcome.record.model_identity == "ollama:qwen2.5:7b"
    assert outcome.record.exit_code is None
    assert (records / "provider.stdout.jsonl").read_text(encoding="utf-8") == "partial stdout"
    assert (records / "provider.stderr.txt").read_text(encoding="utf-8") == "partial stderr"
    assert json.loads((records / "provider_record.json").read_text(encoding="utf-8"))["status"] == "timeout"


def test_provider_missing_executable_is_unavailable(monkeypatch, tmp_path: Path):
    def fake_run(command, **kwargs):
        raise FileNotFoundError("codex not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    records = tmp_path / "records"
    outcome = CodexOfficeProvider(WorkAgentConfig()).run("prompt", tmp_path, records)

    assert outcome.status == "unavailable"
    assert outcome.response is None
    assert outcome.record is not None
    assert outcome.record.model_identity == "ollama:qwen2.5:7b"
    assert outcome.record.exit_code is None
    assert "codex not found" in (outcome.error or "")
    assert (records / "provider.stdout.jsonl").read_text(encoding="utf-8") == ""
    assert (records / "provider.stderr.txt").read_text(encoding="utf-8") == ""
    assert json.loads((records / "provider_record.json").read_text(encoding="utf-8"))["status"] == "unavailable"


def test_provider_reused_record_root_does_not_accept_stale_response(monkeypatch, tmp_path: Path):
    records = tmp_path / "records"
    response = {"status": "completed", "deliverables": [], "summary": "first run", "input_files_used": []}
    calls = []

    def fake_run(command, **kwargs):
        output_path = Path(command[command.index("--output-last-message") + 1])
        calls.append(output_path)
        if len(calls) == 1:
            output_path.write_text(json.dumps(response), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    provider = CodexOfficeProvider(WorkAgentConfig())
    first = provider.run("first", tmp_path, records)
    second = provider.run("second", tmp_path, records)

    assert first.status == "completed"
    assert second.status == "failed"
    assert second.response is None
    assert second.record is not None
    assert second.record.output_ref is None
    assert calls[0] != calls[1]
    assert calls[0].exists()
    assert json.loads(calls[0].read_text(encoding="utf-8")) == response
    assert not (tmp_path / "agent_response.json").exists()


def _office_task(domain="excel", input_files=()):
    return TaskSpec(task_id="pilot-1", domain=domain, instruction="Build a report", input_files=input_files)


def test_input_copy_preserves_original_and_records_private_hashes(tmp_path: Path):
    input_base = tmp_path / "sources"
    input_base.mkdir()
    source = input_base / "source.xlsx"
    workbook = Workbook()
    workbook.active["A1"] = "original"
    workbook.save(source)
    before = sha256_file(source)
    workspace = tmp_path / "workspace"

    manifest = copy_task_inputs(_office_task(input_files=("source.xlsx",)), workspace, input_base)

    copied = workspace / "inputs/0001-source.xlsx"
    assert copied.is_file()
    assert sha256_file(source) == before == sha256_file(copied)
    assert manifest["files"][0]["source_sha256"] == before
    assert manifest["files"][0]["copy_sha256"] == before
    assert manifest["files"][0]["copied"] == "inputs/0001-source.xlsx"
    assert json.loads((workspace / "input_manifest.json").read_text(encoding="utf-8")) == manifest
    assert str(input_base) not in json.dumps(manifest)


def test_input_copy_rejects_cross_domain_and_nonregular_files(tmp_path: Path):
    source = tmp_path / "source.docx"
    Document().save(source)
    with pytest.raises(ValueError):
        copy_task_inputs(_office_task(input_files=("source.docx",)), tmp_path / "workspace", tmp_path)
    (tmp_path / "folder.xlsx").mkdir()
    with pytest.raises(ValueError):
        copy_task_inputs(_office_task(input_files=("folder.xlsx",)), tmp_path / "workspace", tmp_path)


@pytest.mark.parametrize("name", ["../source.xlsx", "missing.xlsx", "source.xls", "//server/share/source.xlsx", "C:/source.xlsx", "/source.xlsx"])
def test_input_copy_rejects_unsafe_or_unsupported_paths(tmp_path: Path, name: str):
    with pytest.raises(ValueError):
        copy_task_inputs(_office_task(input_files=(name,)), tmp_path / "workspace", tmp_path)


def test_input_copy_rejects_symlinked_parent(tmp_path: Path):
    real = tmp_path / "real"
    real.mkdir()
    Workbook().save(real / "source.xlsx")
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    with pytest.raises(ValueError):
        copy_task_inputs(_office_task(input_files=("link/source.xlsx",)), tmp_path / "workspace", tmp_path)


def test_input_copy_rejects_preexisting_destination_symlink(tmp_path: Path):
    Workbook().save(tmp_path / "source.xlsx")
    workspace = tmp_path / "workspace"
    (workspace / "inputs").mkdir(parents=True)
    destination = workspace / "inputs/0001-source.xlsx"
    try:
        destination.symlink_to(tmp_path / "source.xlsx")
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    with pytest.raises(ValueError):
        copy_task_inputs(_office_task(input_files=("source.xlsx",)), workspace, tmp_path)


@pytest.mark.parametrize("which", ["source", "copy"])
def test_input_hash_verification_rejects_post_provider_tampering(tmp_path: Path, which: str):
    source = tmp_path / "source.xlsx"
    Workbook().save(source)
    workspace = tmp_path / "workspace"
    task = _office_task(input_files=("source.xlsx",))
    manifest = copy_task_inputs(task, workspace, tmp_path)
    verify_task_input_hashes(task, workspace, tmp_path, manifest)
    target = source if which == "source" else workspace / "inputs/0001-source.xlsx"
    target.write_bytes(b"tampered")
    with pytest.raises(ValueError):
        verify_task_input_hashes(task, workspace, tmp_path, manifest)


def test_task_prompt_does_not_expose_evaluator_constraints_or_source_paths(tmp_path: Path):
    secret_path = str(tmp_path / "secret-source.xlsx")
    task = TaskSpec(task_id="pilot-1", domain="excel", instruction="Build an expense workbook",
                    input_files=(secret_path,), expected_constraints={"required_cells": {"Summary!B2": 999}})
    prompt = build_task_prompt(task, {"files": [{"copied": "inputs/0001-source.xlsx", "source": "source.xlsx"}]},
                               "Use clear sheet names")
    assert "Build an expense workbook" in prompt
    assert "excel" in prompt and "inputs/0001-source.xlsx" in prompt
    assert "outputs/" in prompt and "deliverables.json" in prompt
    assert "Use clear sheet names" in prompt
    assert "999" not in prompt and "expected_constraints" not in prompt
    assert secret_path not in prompt


def _deliverable_fixture(tmp_path: Path, paths=("outputs/report.xlsx",)):
    workspace = tmp_path / "workspace"
    (workspace / "outputs").mkdir(parents=True)
    response = AgentResponse(status="completed", deliverables=list(paths), summary="done", input_files_used=[])
    (workspace / "agent_response.json").write_text(response.model_dump_json(), encoding="utf-8")
    (workspace / "deliverables.json").write_text(json.dumps({"deliverables": list(paths)}), encoding="utf-8")
    for path in paths:
        if path.startswith("outputs/") and ".." not in path:
            target = workspace / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"office package")
    return workspace, response


def test_deliverable_accepts_only_manifested_domain_file(tmp_path: Path):
    workspace, response = _deliverable_fixture(tmp_path)
    assert validate_deliverables(_office_task(), workspace, response, WorkAgentConfig()) == [workspace / "outputs/report.xlsx"]


@pytest.mark.parametrize("path", ["outputs/../outside.xlsx", "C:/outside.xlsx", "/outside.xlsx", "outputs/report.docx"])
def test_deliverable_rejects_unsafe_path_or_cross_format(tmp_path: Path, path: str):
    workspace, response = _deliverable_fixture(tmp_path)
    (workspace / "deliverables.json").write_text(json.dumps({"deliverables": [path]}), encoding="utf-8")
    with pytest.raises(ValueError):
        validate_deliverables(_office_task(), workspace, response, WorkAgentConfig())


def test_deliverable_rejects_unlisted_output_and_missing_manifest(tmp_path: Path):
    workspace, response = _deliverable_fixture(tmp_path)
    (workspace / "deliverables.json").write_text(json.dumps({"deliverables": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        validate_deliverables(_office_task(), workspace, response, WorkAgentConfig())
    (workspace / "deliverables.json").unlink()
    with pytest.raises(ValueError):
        validate_deliverables(_office_task(), workspace, response, WorkAgentConfig())


def test_deliverable_rejects_symlink_empty_and_oversize(tmp_path: Path):
    workspace, response = _deliverable_fixture(tmp_path)
    output = workspace / "outputs/report.xlsx"
    output.write_bytes(b"")
    with pytest.raises(ValueError):
        validate_deliverables(_office_task(), workspace, response, WorkAgentConfig())
    output.write_bytes(b"too large")
    with pytest.raises(ValueError):
        validate_deliverables(_office_task(), workspace, response, WorkAgentConfig(max_artifact_bytes=3))
    output.unlink()
    target = tmp_path / "outside.xlsx"
    target.write_bytes(b"content")
    try:
        output.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    with pytest.raises(ValueError):
        validate_deliverables(_office_task(), workspace, response, WorkAgentConfig())


def test_deliverable_rejects_file_count_and_malformed_response(tmp_path: Path):
    workspace, response = _deliverable_fixture(tmp_path, ("outputs/one.xlsx", "outputs/two.xlsx"))
    with pytest.raises(ValueError):
        validate_deliverables(_office_task(), workspace, response, WorkAgentConfig(max_output_files=1))
    (workspace / "agent_response.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        validate_deliverables(_office_task(), workspace, response, WorkAgentConfig())
