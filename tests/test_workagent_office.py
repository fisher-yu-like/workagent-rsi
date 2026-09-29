import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from workagent_rsi.hashing import canonical_json_hash, sha256_file
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
    assert outcome.record.output_ref == sha256_file(records / "agent_response.json")
    assert observed["input"] == "make a report"
    assert observed["capture_output"] is True
    assert observed["text"] is True
    assert observed["timeout"] == 600
    assert observed["command"][-1] == "-"
    assert (records / "prompt.txt").read_text(encoding="utf-8") == "make a report"
    assert (records / "provider.stdout.jsonl").read_text(encoding="utf-8") == '{"type":"done"}\n'
    assert (records / "provider.stderr.txt").read_text(encoding="utf-8") == "notice\n"
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
