import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from workagent_rsi.candidate_provider import CodexCandidateProvider, DeterministicCandidateProvider
from workagent_rsi.rsi_contracts import FailureDiagnosis


def diagnosis() -> FailureDiagnosis:
    return FailureDiagnosis(
        diagnosis_id="d1",
        run_ids=["r1"],
        failure_class="semantic",
        evidence_refs=["a" * 64],
        causal_hypothesis="required marker omitted",
        recommended_component="prompt",
        confidence=0.9,
    )


def candidate_payload() -> dict:
    return {
        "candidate_id": "candidate-1",
        "parent_version": "0.1.0",
        "provider": "codex-cli",
        "provider_version": "0.144.2",
        "model_identity": None,
        "diagnosis_refs": ["a" * 64],
        "atomic_edits": [
            {
                "component": "prompt",
                "target_path": "skill.json",
                "hypothesis": "use required marker",
                "expected_metric": "task_success_rate",
                "patch": '{"marker_source":"required_text"}',
            }
        ],
        "new_tests": [],
        "edit_budget": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def test_codex_provider_constructs_isolated_structured_command(tmp_path: Path):
    calls = []

    def runner(command, cwd, timeout):
        calls.append((command, cwd, timeout))
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(candidate_payload()), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout='{"type":"done"}\n', stderr="")

    provider = CodexCandidateProvider(
        schema_path=tmp_path / "schema.json",
        provider_version="0.144.2",
        extra_args=["--ignore-user-config", "--oss", "--local-provider", "ollama", "--model", "qwen2.5:7b"],
        runner=runner,
    )
    (tmp_path / "schema.json").write_text("{}", encoding="utf-8")
    patch, record = provider.generate(tmp_path, [diagnosis()], "0.1.0", 1, tmp_path / "records")

    command = calls[0][0]
    assert patch is not None
    assert record.status == "completed"
    assert "--ephemeral" in command
    assert "--ignore-user-config" in command
    assert command[command.index("--local-provider") + 1] == "ollama"
    assert command[command.index("--sandbox") + 1] == "workspace-write"
    assert command[command.index("--output-schema") + 1].endswith("schema.json")
    assert command[command.index("--cd") + 1] == str(tmp_path)
    assert '{"marker_source":"required_text"}' in command[-1]


def test_codex_provider_records_invalid_json(tmp_path: Path):
    def runner(command, cwd, timeout):
        Path(command[command.index("--output-last-message") + 1]).write_text("not-json", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    schema = tmp_path / "schema.json"
    schema.write_text("{}", encoding="utf-8")
    patch, record = CodexCandidateProvider(schema, "0.144.2", runner=runner).generate(
        tmp_path, [diagnosis()], "0.1.0", 1, tmp_path / "records"
    )
    assert patch is None
    assert record.status == "failed"
    assert "JSON" in (record.error or "")


def test_codex_provider_records_timeout(tmp_path: Path):
    def runner(command, cwd, timeout):
        raise subprocess.TimeoutExpired(command, timeout)

    schema = tmp_path / "schema.json"
    schema.write_text("{}", encoding="utf-8")
    patch, record = CodexCandidateProvider(schema, "0.144.2", runner=runner).generate(
        tmp_path, [diagnosis()], "0.1.0", 1, tmp_path / "records"
    )
    assert patch is None
    assert record.status == "timeout"


def test_deterministic_provider_returns_real_contract(tmp_path: Path):
    patch, record = DeterministicCandidateProvider().generate(
        tmp_path, [diagnosis()], "0.1.0", 1, tmp_path / "records"
    )
    assert patch.atomic_edits[0].target_path == "skill.json"
    assert record.status == "completed"
