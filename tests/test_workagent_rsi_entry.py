"""Fail-closed qualification gate for the real WorkAgent RSI entry point."""

import importlib.util
import json
from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "project_artifacts/phase3_experiments/scripts/run_workagent_rsi.py"


@pytest.fixture(autouse=True)
def forbid_historical_results(monkeypatch):
    """Unit tests must remain runnable without ignored qualification records."""
    original = Path.open
    historical = ROOT / "project_artifacts/results/qualification"

    def guarded(path, *args, **kwargs):
        assert not path.resolve().is_relative_to(historical.resolve()), "unit test read ignored historical evidence"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)


def _fake_com(path, domain):
    return {"ok": True, "status": "available", "version": "16.0"}


def _module():
    spec = importlib.util.spec_from_file_location("run_workagent_rsi", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def baseline(tmp_path, monkeypatch):
    """Create representative failed evidence through the real pilot/Harness path."""
    from project_artifacts.phase3_experiments.scripts import run_general_office_pilot as pilot
    from workagent_rsi.office_capabilities import CapabilityReport
    from workagent_rsi.workagent_provider import CodexOfficeProvider, ProviderOutcome

    result_root = tmp_path / "qualification"
    monkeypatch.setattr(pilot, "RESULT_ROOT", result_root)
    monkeypatch.setattr(pilot, "probe_capabilities", CapabilityReport.for_testing)
    monkeypatch.setattr(CodexOfficeProvider, "run", lambda *args: ProviderOutcome(status="failed", error="fixture: no deliverables"))
    assert pilot.main([]) == 1
    return next(result_root.iterdir())


def test_real_failed_baseline_blocks_before_runner_and_preserves_contract(tmp_path, baseline):
    """Removing the gate would call the forbidden model runner on the 0/6 baseline."""
    module = _module()

    def forbidden(*args, **kwargs):
        raise AssertionError("RSI runner must not start")

    result = module.run_invocation(baseline, tmp_path / "invocation", runner_factory=forbidden, source_com_verify=_fake_com)
    assert result == 1
    summary = json.loads((tmp_path / "invocation/summary.json").read_text(encoding="utf-8"))
    contract = json.loads((tmp_path / "invocation/contract.json").read_text(encoding="utf-8"))
    assert summary["status"] == "blocked"
    assert summary["baseline"]["success_count"] == 0
    assert summary["baseline"]["failure_count"] == 6
    assert contract["seed"] == 20260930
    assert len(contract["split_hashes"]) == 4
    assert len(contract["source_input_hashes"]) == 3
    assert contract["model_identity"] == "ollama:qwen2.5:7b"
    office = json.loads((tmp_path / "invocation/source_office_validation.json").read_text(encoding="utf-8"))
    assert office["scope"] == "generated_source_inputs_not_workagent_outputs"
    assert {row["domain"] for row in office["files"]} == {"excel", "word", "powerpoint"}
    assert all(row["library_reopen_ok"] and row["com_reopen"]["ok"] and row["sha256"] == contract["source_input_hashes"][row["name"]] for row in office["files"])
    assert (tmp_path / "invocation/analysis.json").is_file()
    assert "阻断" in (tmp_path / "invocation/qualification_report.md").read_text(encoding="utf-8")


def test_tampered_baseline_row_is_rejected_before_runner(tmp_path, baseline):
    """A summary-only success edit must not make qualification eligible."""
    module = _module()
    summary = json.loads((baseline / "summary.json").read_text(encoding="utf-8"))
    summary["rows"][0]["state"] = "SUCCEEDED"
    summary["success_count"] = 1
    summary["failure_count"] = 5
    (baseline / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    result = module.run_invocation(baseline, tmp_path / "result", runner_factory=lambda: (_ for _ in ()).throw(AssertionError("runner called")), source_com_verify=_fake_com)
    assert result == 1
    saved = json.loads((tmp_path / "result/summary.json").read_text(encoding="utf-8"))
    assert saved["status"] == "blocked"
    assert "persisted row mismatch" in saved["block_reason"]


def test_qualified_baseline_wires_one_bounded_round_with_mocked_run(tmp_path, monkeypatch, baseline):
    """A valid gate must keep the real RSI interface reachable without a model call."""
    module = _module()
    monkeypatch.setattr(module, "validate_baseline", lambda path: ({"success_count": 6, "failure_count": 0, "task_count": 6}, []))

    class FakeRunner:
        def __init__(self, *, workagent_config, input_base):
            assert workagent_config.model == "qwen2.5:7b"
            assert workagent_config.backend == "ollama-native"
            assert input_base.name == "inputs"

        def run(self, tasks, skill, provider, output_root, *, rounds):
            assert rounds == 1
            assert {key: len(value) for key, value in tasks.items()} == {"develop": 3, "regression": 3, "hidden": 3, "ood_transfer": 3}
            assert skill.instructions
            assert isinstance(provider, module.OllamaWorkAgentCandidateProvider)
            assert provider.model == "qwen2.5:7b"
            contract = json.loads((output_root.parent / "contract.json").read_text(encoding="utf-8"))
            matrix = output_root.parent / "rsi_tasks.json"
            assert matrix.read_bytes() == module.CONFIG.read_bytes()
            assert contract["task_config_sha256"] == module.sha256_file(matrix)
            assert contract["split_hashes"] == {
                split: module.canonical_json_hash([task.model_dump(mode="json") for task in rows])
                for split, rows in tasks.items()
            }
            return {"status": "completed", "accepted": 0}

    output = tmp_path / "eligible"
    assert module.run_invocation(baseline, output, runner_factory=FakeRunner, source_com_verify=_fake_com) == 0
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["rsi_started"] is True
    assert summary["rsi_result"]["accepted"] == 0


@pytest.mark.parametrize("malformed", [False, True])
def test_missing_or_malformed_baseline_summary_still_writes_blocked_reports(tmp_path, malformed):
    """A failed preflight read must not escape before persisted block evidence."""
    module = _module()
    baseline = tmp_path / "bad-baseline"
    baseline.mkdir()
    if malformed:
        (baseline / "summary.json").write_text("{bad", encoding="utf-8")
    output = tmp_path / "result"
    assert module.run_invocation(baseline, output, runner_factory=lambda **kwargs: (_ for _ in ()).throw(AssertionError("model called")), source_com_verify=_fake_com) == 1
    assert json.loads((output / "summary.json").read_text(encoding="utf-8"))["status"] == "blocked"
    saved_hash = json.loads((output / "contract.json").read_text(encoding="utf-8"))["baseline_summary_sha256"]
    assert (saved_hash is None) if not malformed else (isinstance(saved_hash, str) and len(saved_hash) == 64)
    assert (output / "analysis.json").is_file()
    assert "阻断" in (output / "qualification_report.md").read_text(encoding="utf-8")


def test_runner_exception_preserves_partial_evidence_and_failed_reports(tmp_path, monkeypatch, baseline):
    """An eligible-run crash must not erase nested artifacts or omit aggregate reports."""
    module = _module()
    monkeypatch.setattr(module, "validate_baseline", lambda path: ({"success_count": 6, "failure_count": 0, "task_count": 6}, []))

    class CrashingRunner:
        def __init__(self, **kwargs):
            pass

        def run(self, tasks, skill, provider, output_root, *, rounds):
            output_root.mkdir(parents=True)
            (output_root / "partial.txt").write_text("kept", encoding="utf-8")
            raise RuntimeError("run failed")

    output = tmp_path / "result"
    assert module.run_invocation(baseline, output, runner_factory=CrashingRunner, source_com_verify=_fake_com) == 1
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "failed"
    assert summary["rsi_started"] is True
    assert (output / "rsi/partial.txt").read_text(encoding="utf-8") == "kept"
    assert json.loads((output / "analysis.json").read_text(encoding="utf-8"))["status"] == "failed"
    assert "失败" in (output / "qualification_report.md").read_text(encoding="utf-8")


def test_incomplete_result_exits_nonzero_and_detects_candidate_evidence(tmp_path, monkeypatch, baseline):
    """An incomplete RSI return is not reported as completed or successful."""
    module = _module()
    monkeypatch.setattr(module, "validate_baseline", lambda path: ({"success_count": 6, "failure_count": 0, "task_count": 6}, []))

    class IncompleteRunner:
        def __init__(self, **kwargs):
            pass

        def run(self, tasks, skill, provider, output_root, *, rounds):
            evidence = output_root / "rounds/round-01/provider_records"
            evidence.mkdir(parents=True)
            (evidence / "provider_record.json").write_text("{}", encoding="utf-8")
            (output_root.parent / "candidate_launch_attempt.json").write_text('{"command": ["codex", "exec"]}', encoding="utf-8")
            return {"status": "incomplete", "incomplete_round": {"status": "unavailable"}}

    output = tmp_path / "result"
    assert module.run_invocation(baseline, output, runner_factory=IncompleteRunner, source_com_verify=_fake_com) == 1
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "incomplete"
    assert summary["candidate_started"] is True


def test_baseline_selector_accepts_direct_id_only(tmp_path, monkeypatch):
    """A future qualified invocation may be selected, but traversal cannot escape results."""
    module = _module()
    monkeypatch.setattr(module, "RESULT_ROOT", tmp_path)
    eligible = tmp_path / "20260930T000000Z-1234abcd"
    eligible.mkdir()
    assert module.resolve_baseline_invocation(eligible.name) == eligible
    for unsafe in ("../outside", str(eligible), "bad-id"):
        with pytest.raises(ValueError):
            module.resolve_baseline_invocation(unsafe)


def test_unreadable_baseline_summary_hash_still_blocks(tmp_path, monkeypatch, baseline):
    """An OSError while hashing baseline evidence must not prevent reports."""
    module = _module()
    original = module.sha256_file

    def unreadable(path):
        if Path(path) == baseline / "summary.json":
            raise OSError("read denied")
        return original(path)

    monkeypatch.setattr(module, "sha256_file", unreadable)
    output = tmp_path / "result"
    assert module.run_invocation(baseline, output, runner_factory=lambda **kwargs: (_ for _ in ()).throw(AssertionError("model called")), source_com_verify=_fake_com) == 1
    assert json.loads((output / "summary.json").read_text(encoding="utf-8"))["status"] == "blocked"


def test_source_com_exception_persists_failed_validation_and_blocked_reports(tmp_path, baseline):
    """A source validation probe failure must not escape before aggregate reports."""
    module = _module()

    def broken_com(path, domain):
        raise OSError("COM unavailable")

    output = tmp_path / "result"
    assert module.run_invocation(baseline, output, runner_factory=lambda **kwargs: (_ for _ in ()).throw(AssertionError("model called")), source_com_verify=broken_com) == 1
    validation = json.loads((output / "source_office_validation.json").read_text(encoding="utf-8"))
    assert validation["passed"] is False
    assert json.loads((output / "summary.json").read_text(encoding="utf-8"))["status"] == "blocked"


def test_candidate_launch_permission_error_counts_as_attempt_without_provider_record(tmp_path, monkeypatch, baseline):
    """A native request setup exception after the attempt boundary remains visible."""
    module = _module()
    monkeypatch.setattr(module, "validate_baseline", lambda path: ({"success_count": 6, "failure_count": 0, "task_count": 6}, []))

    class LaunchingRunner:
        def __init__(self, **kwargs):
            pass

        def run(self, tasks, skill, provider, output_root, *, rounds):
            provider.before_request(["POST", "http://localhost:11434/api/chat", "--model", "qwen2.5:7b"])
            raise PermissionError("request launch denied")

    output = tmp_path / "result"
    assert module.run_invocation(baseline, output, runner_factory=LaunchingRunner, source_com_verify=_fake_com) == 1
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "failed"
    assert summary["candidate_started"] is True
    assert json.loads((output / "candidate_launch_attempt.json").read_text(encoding="utf-8"))["command"] == ["POST", "http://localhost:11434/api/chat", "--model", "qwen2.5:7b"]
    assert not list(output.rglob("provider_record.json"))
    assert json.loads((output / "analysis.json").read_text(encoding="utf-8"))["candidate_started"] is True


def test_baseline_provider_records_do_not_claim_candidate_started(tmp_path, monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "validate_baseline", lambda path: ({"success_count": 6, "failure_count": 0, "task_count": 6}, []))

    class BaselineOnlyRunner:
        def __init__(self, **kwargs):
            pass

        def run(self, tasks, skill, provider, output_root, *, rounds):
            records = output_root / "rounds/round-01/baseline/develop/task/run/provider_records"
            records.mkdir(parents=True)
            (records / "provider_record.json").write_text('{"provider": "codex-cli"}', encoding="utf-8")
            return {"status": "no_candidate_needed"}

    baseline = tmp_path / "baseline"
    output = tmp_path / "result"
    assert module.run_invocation(baseline, output, runner_factory=BaselineOnlyRunner, source_com_verify=_fake_com) == 0
    assert json.loads((output / "summary.json").read_text(encoding="utf-8"))["candidate_started"] is False
    assert json.loads((output / "analysis.json").read_text(encoding="utf-8"))["candidate_started"] is False
