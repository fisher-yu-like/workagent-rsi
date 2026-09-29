import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from workagent_rsi.workagent_provider import (
    AgentResponse,
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
