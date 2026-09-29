import json
import subprocess
from pathlib import Path

import pytest
import yaml
from docx import Document
from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Inches
from pydantic import ValidationError

from workagent_rsi.contracts import TaskSpec
from workagent_rsi.cli import main as cli_main
from workagent_rsi.hashing import canonical_json_hash, sha256_file
from workagent_rsi.harness import Harness
from workagent_rsi.office_checks import inspect_office_file
from workagent_rsi.workagent_office import build_task_prompt, copy_task_inputs, validate_deliverables, verify_task_input_hashes
from workagent_rsi.workagent_provider import (
    AgentResponse,
    CodexOfficeProvider,
    ProviderOutcome,
    WorkAgentConfig,
    build_agent_response_schema,
)


def test_cli_accepts_explicit_workagent_provider(monkeypatch, tmp_path: Path):
    task_file = tmp_path / "task.yaml"
    task_file.write_text(yaml.safe_dump({"task_id": "cli-explicit", "domain": "excel", "instruction": "Create a workbook"}), encoding="utf-8")

    def missing_provider(command, **kwargs):
        raise FileNotFoundError("codex not found")

    monkeypatch.setattr(subprocess, "run", missing_provider)
    exit_code = cli_main([str(task_file), "--results-dir", str(tmp_path / "results"), "--execution-provider", "workagent"])

    assert exit_code == 1
    result = json.loads(next((tmp_path / "results").glob("*/result.json")).read_text(encoding="utf-8"))
    assert result["state"] == "UNAVAILABLE"


def test_cli_defaults_office_tasks_to_workagent(monkeypatch, tmp_path: Path):
    task_file = tmp_path / "task.yaml"
    task_file.write_text(yaml.safe_dump({"task_id": "cli-default", "domain": "excel", "instruction": "Create a workbook"}), encoding="utf-8")

    def missing_provider(command, **kwargs):
        raise FileNotFoundError("codex not found")

    monkeypatch.setattr(subprocess, "run", missing_provider)
    exit_code = cli_main([str(task_file), "--results-dir", str(tmp_path / "results")])

    assert exit_code == 1
    result = json.loads(next((tmp_path / "results").glob("*/result.json")).read_text(encoding="utf-8"))
    assert result["state"] == "UNAVAILABLE"


def test_cli_resolves_relative_input_files_from_task_yaml_directory(monkeypatch, tmp_path: Path):
    task_dir = tmp_path / "task-directory"
    task_dir.mkdir()
    Workbook().save(task_dir / "source.xlsx")
    task_file = task_dir / "task.yaml"
    task_file.write_text(yaml.safe_dump({"task_id": "cli-input", "domain": "excel", "instruction": "Edit the workbook", "input_files": ["source.xlsx"]}), encoding="utf-8")
    monkeypatch.chdir(Path(__file__).resolve().parents[1])

    def missing_provider(command, **kwargs):
        raise FileNotFoundError("codex not found")

    monkeypatch.setattr(subprocess, "run", missing_provider)
    exit_code = cli_main([str(task_file), "--results-dir", str(tmp_path / "results")])

    assert exit_code == 1
    result_file = next((tmp_path / "results").glob("*/result.json"))
    assert json.loads(result_file.read_text(encoding="utf-8"))["state"] == "UNAVAILABLE"
    manifest = json.loads((result_file.parent / "agent_workspace/input_manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"][0]["source"] == "source.xlsx"
    assert (result_file.parent / "agent_workspace/inputs/0001-source.xlsx").is_file()


def test_cli_accepts_output_inside_selected_results_run_directory(tmp_path: Path):
    task_file = tmp_path / "task.yaml"
    task_file.write_text(yaml.safe_dump({"task_id": "cli-output", "domain": "smoke", "instruction": "Run smoke task"}), encoding="utf-8")
    results_dir = tmp_path / "custom-results"
    output = results_dir / "run-one" / "result.json"

    exit_code = cli_main([str(task_file), "--results-dir", str(results_dir), "--output", str(output)])

    assert exit_code == 0
    assert output.is_file()
    assert json.loads(output.read_text(encoding="utf-8"))["result_dir"] == str(output.parent.resolve())


@pytest.mark.parametrize("kind", ["outside", "traversal"])
def test_cli_rejects_results_dir_outside_project_results(tmp_path: Path, kind: str):
    task_file = tmp_path / "task.yaml"
    task_file.write_text(yaml.safe_dump({"task_id": "cli-results-boundary", "domain": "smoke", "instruction": "Run smoke task"}), encoding="utf-8")
    results_root = Path(__file__).resolve().parents[1] / "project_artifacts/results"
    target = results_root.parent / f"escaped-results-{tmp_path.name}"
    results_dir = target if kind == "outside" else results_root / ".." / target.name

    with pytest.raises(SystemExit) as exc:
        cli_main([str(task_file), "--results-dir", str(results_dir)])

    assert exc.value.code == 2
    assert not target.exists()


@pytest.mark.parametrize("kind", ["outside", "traversal", "results_root"])
def test_cli_rejects_output_outside_per_run_directory(tmp_path: Path, kind: str):
    task_file = tmp_path / "task.yaml"
    task_file.write_text(yaml.safe_dump({"task_id": "cli-output-boundary", "domain": "smoke", "instruction": "Run smoke task"}), encoding="utf-8")
    results_dir = tmp_path / "custom-results"
    if kind == "outside":
        output = results_dir.parent / "escaped-result.json"
    elif kind == "traversal":
        output = results_dir / "run-one" / ".." / ".." / "escaped-result.json"
    else:
        output = results_dir / "result.json"

    with pytest.raises(SystemExit) as exc:
        cli_main([str(task_file), "--results-dir", str(results_dir), "--output", str(output)])

    assert exc.value.code == 2
    assert not results_dir.exists()


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


@pytest.mark.parametrize("name", ["../source.xlsx", "missing.xlsx", "source.xls", "//server/share/source.xlsx", r"\\server\share\source.xlsx"])
def test_input_copy_rejects_unsafe_or_unsupported_paths(tmp_path: Path, name: str):
    with pytest.raises(ValueError):
        copy_task_inputs(_office_task(input_files=(name,)), tmp_path / "workspace", tmp_path)


def test_input_copy_accepts_explicit_local_absolute_path_without_leaking_it(tmp_path: Path):
    input_base = tmp_path / "unused-base"
    input_base.mkdir()
    source = tmp_path / "provided" / "source.xlsx"
    source.parent.mkdir()
    Workbook().save(source)
    task = _office_task(input_files=(str(source),))
    workspace = tmp_path / "workspace"

    manifest = copy_task_inputs(task, workspace, input_base)
    verify_task_input_hashes(task, workspace, input_base, manifest)
    prompt = build_task_prompt(task, manifest, "Use clear sheet names")

    assert sha256_file(workspace / "inputs/0001-source.xlsx") == sha256_file(source)
    assert str(source) not in json.dumps(manifest)
    assert str(source) not in (workspace / "input_manifest.json").read_text(encoding="utf-8")
    assert str(source) not in prompt


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


def _harness_excel_task(input_files=()):
    return TaskSpec(
        task_id="harness-excel",
        domain="excel",
        instruction="Create a Summary workbook with B2 set to 42",
        input_files=input_files,
        expected_constraints={"required_cells": {"Summary!B2": 42}},
    )


def test_harness_workagent_stores_validated_excel_and_provider_trace(monkeypatch, tmp_path: Path):
    source = tmp_path / "source.xlsx"
    Workbook().save(source)
    source_hash = sha256_file(source)

    def fake_run(command, **kwargs):
        workspace = Path(command[command.index("--cd") + 1])
        assert kwargs["cwd"] == workspace
        assert (workspace / "inputs/0001-source.xlsx").is_file()
        assert "Summary workbook" in kwargs["input"]
        output = workspace / "outputs/report.xlsx"
        output.parent.mkdir()
        workbook = Workbook()
        workbook.active.title = "Summary"
        workbook.active["B2"] = 42
        workbook.save(output)
        response = {"status": "completed", "deliverables": ["outputs/report.xlsx"],
                    "summary": "Created workbook", "input_files_used": ["inputs/0001-source.xlsx"]}
        (workspace / "deliverables.json").write_text(json.dumps({"deliverables": response["deliverables"]}), encoding="utf-8")
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(response), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout='{"type":"done"}\n', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    harness = Harness(tmp_path / "results", execution_provider="workagent", workagent_config=WorkAgentConfig())
    result = harness.run(_harness_excel_task((str(source),)))

    assert result["state"] == "SUCCEEDED"
    assert result["evaluation"]["passed"] is True
    assert sha256_file(source) == source_hash
    assert len(result["artifacts"]) == 1
    artifact = Path(result["artifacts"][0]["path"])
    assert artifact.is_file() and artifact.parent == Path(result["result_dir"]) / "artifacts"
    assert artifact.read_bytes() == (Path(result["result_dir"]) / "agent_workspace/outputs/report.xlsx").read_bytes()
    assert (Path(result["result_dir"]) / "provider_records/provider_record.json").is_file()
    saved = json.loads(Path(result["result_path"]).read_text(encoding="utf-8"))
    assert saved["run_id"] == result["run_id"] and saved["artifacts"] == result["artifacts"]
    events = harness.resume(result["result_dir"])["events"]
    kinds = [event["kind"] for event in events]
    assert kinds == ["run_started", "started", "input_manifest", "provider_output", "artifact"]
    provider = events[3]["payload"]
    assert provider["record"]["provider"] == "codex-cli"
    assert provider["record"]["model_identity"] == "ollama:qwen2.5:7b"


def test_harness_workagent_unavailable_does_not_fall_back_to_template(monkeypatch, tmp_path: Path):
    def missing_provider(command, **kwargs):
        raise FileNotFoundError("codex not found")

    monkeypatch.setattr(subprocess, "run", missing_provider)
    result = Harness(tmp_path / "results", execution_provider="workagent").run(_harness_excel_task())

    assert result["state"] == "UNAVAILABLE"
    assert result["artifacts"] == []
    assert "evaluation" not in result
    assert not list((Path(result["result_dir"]) / "artifacts").iterdir())
    kinds = [event["kind"] for event in Harness().resume(result["result_dir"])["events"]]
    assert kinds == ["run_started", "started", "input_manifest", "provider_output", "unavailable"]
    assert not (Path(result["result_dir"]) / "generated").exists()


def test_harness_workagent_timeout_never_evaluates_or_emits_template(monkeypatch, tmp_path: Path):
    def timed_out(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=b"partial")

    monkeypatch.setattr(subprocess, "run", timed_out)
    result = Harness(tmp_path / "results", execution_provider="workagent").run(_harness_excel_task())

    assert result["state"] == "FAILED"
    assert result["failure"]["status"] == "timeout"
    assert result["artifacts"] == [] and "evaluation" not in result
    kinds = [event["kind"] for event in Harness().resume(result["result_dir"])["events"]]
    assert kinds[-1] == "failure" and "artifact" not in kinds
    assert not (Path(result["result_dir"]) / "generated").exists()


@pytest.mark.parametrize("target", ["source", "copy"])
def test_harness_workagent_rejects_input_tampering_after_provider_exit(monkeypatch, tmp_path: Path, target: str):
    source = tmp_path / "source.xlsx"
    Workbook().save(source)

    def tampering_provider(command, **kwargs):
        workspace = Path(command[command.index("--cd") + 1])
        changed = source if target == "source" else workspace / "inputs/0001-source.xlsx"
        changed.write_bytes(b"changed")
        output = workspace / "outputs/report.xlsx"
        output.parent.mkdir()
        workbook = Workbook()
        workbook.active.title = "Summary"
        workbook.active["B2"] = 42
        workbook.save(output)
        response = {"status": "completed", "deliverables": ["outputs/report.xlsx"],
                    "summary": "Created workbook", "input_files_used": ["inputs/0001-source.xlsx"]}
        (workspace / "deliverables.json").write_text(json.dumps({"deliverables": response["deliverables"]}), encoding="utf-8")
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(response), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", tampering_provider)
    result = Harness(tmp_path / "results", execution_provider="workagent").run(_harness_excel_task((str(source),)))

    assert result["state"] == "FAILED"
    assert "input" in result["failure"]["message"]
    assert result["artifacts"] == [] and "evaluation" not in result
    kinds = [event["kind"] for event in Harness().resume(result["result_dir"])["events"]]
    assert kinds[-1] == "failure" and "artifact" not in kinds


def test_harness_default_office_uses_workagent_and_separates_invocations(monkeypatch, tmp_path: Path):
    def missing_provider(command, **kwargs):
        raise FileNotFoundError("codex not found")

    monkeypatch.setattr(subprocess, "run", missing_provider)
    harness = Harness(tmp_path / "results")
    first = harness.run(_harness_excel_task())
    second = harness.run(_harness_excel_task())

    assert first["state"] == second["state"] == "UNAVAILABLE"
    assert first["result_dir"] != second["result_dir"]
    assert Path(first["result_path"]).is_file() and Path(second["result_path"]).is_file()


def test_harness_persisted_task_excludes_evaluator_constraints_and_source_paths(monkeypatch, tmp_path: Path):
    source = tmp_path / "private-source.xlsx"
    Workbook().save(source)

    def missing_provider(command, **kwargs):
        raise FileNotFoundError("codex not found")

    monkeypatch.setattr(subprocess, "run", missing_provider)
    task = TaskSpec(
        task_id="private-task",
        domain="excel",
        instruction="Build a workbook",
        input_files=(str(source),),
        expected_constraints={"required_cells": {"Summary!B2": "PRIVATE-EVALUATOR-ANSWER"}},
    )
    result = Harness(tmp_path / "results", execution_provider="workagent").run(task)

    task_text = (Path(result["result_dir"]) / "task.json").read_text(encoding="utf-8")
    saved = json.loads(task_text)
    assert saved["task_id"] == "private-task" and saved["instruction"] == "Build a workbook"
    assert "expected_constraints" not in saved and "input_files" not in saved
    assert "PRIVATE-EVALUATOR-ANSWER" not in task_text
    assert str(source) not in task_text


def test_harness_provider_permission_error_persists_evidence_and_one_unavailable(monkeypatch, tmp_path: Path):
    def denied_provider(command, **kwargs):
        raise PermissionError("provider launch denied")

    monkeypatch.setattr(subprocess, "run", denied_provider)
    result = Harness(tmp_path / "results", execution_provider="workagent").run(_harness_excel_task())

    assert result["state"] == "UNAVAILABLE"
    assert result["artifacts"] == [] and "evaluation" not in result
    root = Path(result["result_dir"])
    record = json.loads((root / "provider_records/provider_record.json").read_text(encoding="utf-8"))
    assert record["status"] == "unavailable"
    assert "provider launch denied" in record["error"]
    events = Harness().resume(root)["events"]
    kinds = [event["kind"] for event in events]
    assert kinds == ["run_started", "started", "input_manifest", "provider_output", "unavailable"]
    assert events[3]["payload"]["record"] == record
    assert "provider launch denied" in events[4]["payload"]["message"]


def test_evaluator_excel_pilot_checks_sheets_cells_and_formula(tmp_path: Path):
    path = tmp_path / "quarterly.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.title = "Summary"
    sheet["A1"] = "Quarter"
    sheet["B2"] = 120
    sheet["B5"] = "=SUM(B2:B4)"
    book.save(path)
    passing = TaskSpec(task_id="excel-pass", domain="excel", instruction="Create workbook", expected_constraints={
        "required_sheets": ["Summary"], "required_cells": {"Summary!A1": "Quarter", "Summary!B2": 120},
        "required_formulas": {"Summary!B5": "=SUM(B2:B4)"},
    })
    failing = passing.model_copy(update={"expected_constraints": {"required_sheets": ["Missing"]}})
    assert inspect_office_file(path, passing).passed
    assert any("required sheet" in item for item in inspect_office_file(path, failing).failures)


def test_evaluator_word_pilot_checks_headings_styles_and_text(tmp_path: Path):
    path = tmp_path / "status.docx"
    doc = Document()
    doc.add_heading("Status", level=1)
    doc.add_paragraph("Owner: Maya. Action: confirm launch date.")
    doc.save(path)
    passing = TaskSpec(task_id="word-pass", domain="word", instruction="Create report", expected_constraints={
        "required_headings": ["Status"], "required_heading_styles": {"Status": "Heading 1"},
        "required_text": "Action: confirm launch date.",
    })
    failing = passing.model_copy(update={"expected_constraints": {"required_heading_styles": {"Status": "Heading 2"}}})
    assert inspect_office_file(path, passing).passed
    assert any("expected style" in item for item in inspect_office_file(path, failing).failures)


def test_evaluator_powerpoint_pilot_checks_count_text_and_geometry(tmp_path: Path):
    path = tmp_path / "briefing.pptx"
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    shape = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    shape.text = "Launch briefing"
    deck.save(path)
    passing = TaskSpec(task_id="powerpoint-pass", domain="powerpoint", instruction="Create briefing", expected_constraints={
        "required_slide_count": 1, "required_shape_text": ["Launch briefing"],
    })
    failing = passing.model_copy(update={"expected_constraints": {"required_slide_count": 2}})
    report = inspect_office_file(path, passing)
    assert report.passed and report.channel_status["geometry"] == "available"
    assert any("slide count" in item for item in inspect_office_file(path, failing).failures)


def test_general_office_runner_refuses_pilot_before_all_com_apps_available(monkeypatch, tmp_path: Path):
    from project_artifacts.phase3_experiments.scripts import run_general_office_pilot as pilot
    from workagent_rsi.office_capabilities import CapabilityReport

    monkeypatch.setattr(pilot, "RESULT_ROOT", tmp_path)
    monkeypatch.setattr(pilot, "probe_capabilities", lambda: CapabilityReport.for_testing(powerpoint_com=None))
    called = []
    monkeypatch.setattr(pilot, "Harness", lambda *args, **kwargs: called.append("harness"))
    assert pilot.main([]) == 1
    assert called == []
    invocation = next(tmp_path.iterdir())
    assert (invocation / "capability_report.json").is_file()
    summary = json.loads((invocation / "summary.json").read_text(encoding="utf-8"))
    assert summary["task_count"] == 0
    assert "retry_lineage" not in summary
    assert "Retry lineage" not in (invocation / "qualification_report.md").read_text(encoding="utf-8")


def test_general_office_runner_retry_help_and_metadata(monkeypatch, tmp_path: Path, capsys):
    from project_artifacts.phase3_experiments.scripts import run_general_office_pilot as pilot
    from workagent_rsi.office_capabilities import CapabilityReport

    monkeypatch.setattr(pilot, "RESULT_ROOT", tmp_path)
    with pytest.raises(SystemExit) as help_exit:
        pilot.main(["--help"])
    assert help_exit.value.code == 0
    assert "--retry-of" in capsys.readouterr().out

    prior_id = "20260929T190856Z-ab3365c5"
    prior = tmp_path / prior_id
    prior.mkdir()
    prior_summary = {"config_sha256": "a" * 64, "task_count": 6, "success_count": 0, "failure_count": 6}
    prior_bytes = json.dumps(prior_summary).encode("utf-8")
    (prior / "summary.json").write_bytes(prior_bytes)
    monkeypatch.setattr(pilot, "probe_capabilities", lambda: CapabilityReport.for_testing(powerpoint_com=None))

    assert pilot.main(["--retry-of", prior_id]) == 1
    current = next(path for path in tmp_path.iterdir() if path.name != prior_id)
    summary = json.loads((current / "summary.json").read_text(encoding="utf-8"))
    lineage = summary["retry_lineage"]
    assert lineage == {
        "retry_of_invocation_id": prior_id,
        "retry_of_invocation_path": str(prior.resolve()),
        "prior_config_sha256": "a" * 64,
        "prior_task_count": 6,
        "prior_success_count": 0,
        "prior_failure_count": 6,
        "new_config_sha256": sha256_file(pilot.CONFIG),
        "reason": "revised-prompt-and-criteria",
    }
    report = (current / "qualification_report.md").read_text(encoding="utf-8")
    for value in (prior_id, str(prior.resolve()), "a" * 64, lineage["new_config_sha256"], "revised-prompt-and-criteria", "0 succeeded", "6 failed"):
        assert value in report
    assert (prior / "summary.json").read_bytes() == prior_bytes


@pytest.mark.parametrize("prior_id,make_directory", [("", False), ("../outside", False), ("C:/outside", False), ("20260929T190856Z-ab3365c5", True)])
def test_general_office_runner_retry_rejects_path_escape_and_missing_summary(monkeypatch, tmp_path: Path, prior_id: str, make_directory: bool):
    from project_artifacts.phase3_experiments.scripts import run_general_office_pilot as pilot
    from workagent_rsi.office_capabilities import CapabilityReport

    monkeypatch.setattr(pilot, "RESULT_ROOT", tmp_path)
    monkeypatch.setattr(pilot, "probe_capabilities", lambda: CapabilityReport.for_testing(powerpoint_com=None))
    monkeypatch.setattr(pilot, "Harness", lambda *args, **kwargs: pytest.fail("invalid retry must not launch Harness"))
    if make_directory:
        (tmp_path / prior_id).mkdir()
    with pytest.raises(SystemExit) as exc:
        pilot.main(["--retry-of", prior_id])
    assert exc.value.code == 2
    assert sorted(path.name for path in tmp_path.iterdir()) == ([prior_id] if make_directory else [])


@pytest.mark.parametrize("task_id", ["excel-create", "excel-edit", "word-create", "word-edit", "powerpoint-create", "powerpoint-edit"])
def test_evaluator_accepts_and_rejects_exact_general_office_pilot_constraints(tmp_path: Path, task_id: str):
    config_path = Path(__file__).resolve().parents[1] / "project_artifacts/phase3_experiments/configs/general_office_pilot.json"
    item = next(row for row in json.loads(config_path.read_text(encoding="utf-8"))["tasks"] if row["task_id"] == task_id)
    task = TaskSpec(task_id=task_id, domain=item["domain"], instruction=item["instruction"], expected_constraints=item["expected_constraints"])
    if task_id == "excel-create":
        path = tmp_path / "satisfying.xlsx"
        book = Workbook()
        sheet = book.active
        sheet.title = "Summary"
        for cell, value in {"A1": "Quarter", "B1": "Revenue", "A2": "Q1", "B2": 120, "A3": "Q2", "B3": 150, "A4": "Q3", "B4": 180, "A5": "Total", "B5": "=SUM(B2:B4)"}.items():
            sheet[cell] = value
        book.save(path)
        assert inspect_office_file(path, task).passed
        sheet["B5"] = 450
        book.save(path)
        assert any("formula" in failure for failure in inspect_office_file(path, task).failures)
    elif task_id == "excel-edit":
        path = tmp_path / "satisfying.xlsx"
        book = Workbook()
        source = book.active
        source.title = "Transactions"
        for row in (("Item", "Revenue"), ("Alpha", 40), ("Beta", 55), ("Gamma", 65)):
            source.append(row)
        summary = book.create_sheet("Summary")
        summary["A1"], summary["B1"], summary["A2"], summary["B2"] = "Metric", "Amount", "Total Revenue", "=SUM(Transactions!B2:B4)"
        book.save(path)
        assert inspect_office_file(path, task).passed
        source["B3"] = 99
        book.save(path)
        assert any("Transactions!B3" in failure for failure in inspect_office_file(path, task).failures)
    elif task_id in {"word-create", "word-edit"}:
        path = tmp_path / "satisfying.docx"
        doc = Document()
        if task_id == "word-create":
            for title in ("Project Status", "Progress", "Risks", "Next Actions"):
                doc.add_heading(title, level=1)
            body = doc.add_paragraph("Action: confirm launch date with the sponsor by Friday.")
        else:
            for title in ("Executive Summary", "Completed Work"):
                doc.add_heading(title, level=1)
            fact = doc.add_heading("The pilot completed on 12 September.", level=2)
            doc.add_heading("Next Steps", level=1)
            doc.add_paragraph("Action: send the final report to the steering group.")
        doc.save(path)
        assert inspect_office_file(path, task).passed
        if task_id == "word-create":
            body.text = "No action recorded."
            failure_part = "required marker"
        else:
            fact.style = "Heading 1"
            failure_part = "expected style"
        doc.save(path)
        assert any(failure_part in failure for failure in inspect_office_file(path, task).failures)
    else:
        path = tmp_path / "satisfying.pptx"
        deck = Presentation()
        slide_texts = (("Context",), ("Plan",), ("Decision", "Takeaway: approve the phased rollout.")) if task_id == "powerpoint-create" else (("Baseline: two regions",), ("Next step: expand to three regions",))
        boxes = []
        for texts in slide_texts:
            slide = deck.slides.add_slide(deck.slide_layouts[6])
            for index, content in enumerate(texts):
                box = slide.shapes.add_textbox(Inches(1), Inches(1 + 2 * index), Inches(6), Inches(1))
                box.text = content
                boxes.append(box)
        deck.save(path)
        assert inspect_office_file(path, task).passed
        if task_id == "powerpoint-create":
            boxes[0].left = deck.slide_width + Inches(1)
            failure_part = "exceeds slide bounds"
        else:
            boxes[-1].text = "A different next step"
            failure_part = "shape texts are missing"
        deck.save(path)
        assert any(failure_part in failure for failure in inspect_office_file(path, task).failures)


def test_general_office_runner_does_not_com_reopen_failed_evaluation(monkeypatch, tmp_path: Path):
    from project_artifacts.phase3_experiments.scripts import run_general_office_pilot as pilot
    from workagent_rsi.office_capabilities import CapabilityReport

    monkeypatch.setattr(pilot, "RESULT_ROOT", tmp_path)
    monkeypatch.setattr(pilot, "probe_capabilities", CapabilityReport.for_testing)
    monkeypatch.setattr(pilot, "verify_artifact_with_com", lambda *args: pytest.fail("COM must not reopen failed evaluation"))

    class FailedEvaluationHarness:
        def __init__(self, root, **kwargs):
            self.root = root

        def run(self, task, **kwargs):
            run_root = self.root / task.task_id
            run_root.mkdir()
            artifact = run_root / ("invalid" + {"excel": ".xlsx", "word": ".docx", "powerpoint": ".pptx"}[task.domain])
            artifact.write_bytes(b"invalid")
            return {"run_id": task.task_id, "result_dir": str(run_root), "state": "FAILED",
                    "evaluation": {"passed": False, "critical_failures": ["invalid Office structure"]},
                    "artifacts": [{"path": str(artifact), "sha256": "sample"}]}

    monkeypatch.setattr(pilot, "Harness", FailedEvaluationHarness)
    assert pilot.main([]) == 1
    summary = json.loads((next(tmp_path.iterdir()) / "summary.json").read_text(encoding="utf-8"))
    assert summary["task_count"] == 6
    assert all(row["com_ok"] is False for row in summary["rows"])


def test_general_office_runner_records_exception_and_continues_all_six(monkeypatch, tmp_path: Path):
    from project_artifacts.phase3_experiments.scripts import run_general_office_pilot as pilot
    from workagent_rsi.office_capabilities import CapabilityReport

    monkeypatch.setattr(pilot, "RESULT_ROOT", tmp_path)
    monkeypatch.setattr(pilot, "probe_capabilities", CapabilityReport.for_testing)

    class FailingHarness:
        def __init__(self, root, **kwargs):
            self.root = root

        def run(self, task, **kwargs):
            if task.task_id == "excel-edit":
                raise RuntimeError("controlled task exception")
            run_root = self.root / task.task_id
            run_root.mkdir()
            return {"run_id": task.task_id, "result_dir": str(run_root), "state": "FAILED", "artifacts": [],
                    "failure": {"message": "no output"}}

    monkeypatch.setattr(pilot, "Harness", FailingHarness)
    assert pilot.main([]) == 1
    invocation = next(tmp_path.iterdir())
    summary = json.loads((invocation / "summary.json").read_text(encoding="utf-8"))
    assert summary["task_count"] == 6 and len(summary["rows"]) == 6
    assert "controlled task exception" in summary["rows"][1]["failure"]["message"]
    assert (invocation / "excel-edit/qualification_result.json").exists()
    assert summary["rows"][-1]["task_id"] == "powerpoint-edit"


def test_office_prompt_requires_tool_action_before_claiming_completion():
    task = TaskSpec(task_id="prompt", domain="excel", instruction="Create an example workbook")
    prompt = build_task_prompt(task, {"files": []}, "").lower()
    for requirement in ("create a Python script", "run the script", "reopen", "deliverables.json", "status to \"failed\""):
        assert requirement.lower() in prompt
