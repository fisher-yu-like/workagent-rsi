"""Fail-closed qualification gate for the real WorkAgent RSI entry point."""

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "project_artifacts/phase3_experiments/scripts/run_workagent_rsi.py"
BASELINE = ROOT / "project_artifacts/results/qualification/general-office/20260929T195704Z-a4674234"


def _module():
    spec = importlib.util.spec_from_file_location("run_workagent_rsi", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_failed_baseline_blocks_before_runner_and_preserves_contract(tmp_path):
    """Removing the gate would call the forbidden model runner on the 0/6 baseline."""
    module = _module()

    def forbidden(*args, **kwargs):
        raise AssertionError("RSI runner must not start")

    result = module.run_invocation(BASELINE, tmp_path / "invocation", runner_factory=forbidden)
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
    assert (tmp_path / "invocation/analysis.json").is_file()
    assert "阻断" in (tmp_path / "invocation/qualification_report.md").read_text(encoding="utf-8")


def test_tampered_baseline_row_is_rejected_before_runner(tmp_path):
    """A summary-only success edit must not make qualification eligible."""
    module = _module()
    summary = json.loads((BASELINE / "summary.json").read_text(encoding="utf-8"))
    summary["rows"][0]["state"] = "SUCCEEDED"
    summary["success_count"] = 1
    summary["failure_count"] = 5
    tampered = tmp_path / "tampered"
    tampered.mkdir()
    (tampered / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    result = module.run_invocation(tampered, tmp_path / "result", runner_factory=lambda: (_ for _ in ()).throw(AssertionError("runner called")))
    assert result == 1
    saved = json.loads((tmp_path / "result/summary.json").read_text(encoding="utf-8"))
    assert saved["status"] == "blocked"
    assert "evidence" in saved["block_reason"].lower() or "证据" in saved["block_reason"]


def test_qualified_baseline_wires_one_bounded_round_with_mocked_run(tmp_path, monkeypatch):
    """A valid gate must keep the real RSI interface reachable without a model call."""
    module = _module()
    monkeypatch.setattr(module, "validate_baseline", lambda path: ({"success_count": 6, "failure_count": 0, "task_count": 6}, []))

    class FakeRunner:
        def __init__(self, *, workagent_config, input_base):
            assert workagent_config.model == "qwen2.5:7b"
            assert input_base.name == "inputs"

        def run(self, tasks, skill, provider, output_root, *, rounds):
            assert rounds == 1
            assert {key: len(value) for key, value in tasks.items()} == {"develop": 3, "regression": 3, "hidden": 3, "ood_transfer": 3}
            assert skill.instructions
            assert isinstance(provider, module.WorkAgentCandidateProvider)
            return {"status": "completed", "accepted": 0}

    output = tmp_path / "eligible"
    assert module.run_invocation(BASELINE, output, runner_factory=FakeRunner) == 0
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["rsi_started"] is True
    assert summary["rsi_result"]["accepted"] == 0
