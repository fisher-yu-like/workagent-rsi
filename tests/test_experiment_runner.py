import json
from pathlib import Path

from workagent_rsi.candidate_provider import DeterministicCandidateProvider
from workagent_rsi.experiment_runner import ExperimentRunner


def write_task(path: Path, task_id: str, domain: str, split: str, hidden=False):
    row = {
        "task_id": task_id,
        "domain": domain,
        "instruction": f"Create {task_id.upper()}",
        "expected_constraints": {"required_text": task_id.upper()},
        "risk_level": "low",
        "hidden_test": hidden,
        "split": split,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def data_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    write_task(root / "splits" / "evolve.jsonl", "excel-evolve", "excel", "evolve")
    write_task(root / "splits" / "develop.jsonl", "excel-develop", "excel", "develop")
    write_task(root / "splits" / "regression.jsonl", "excel-regression", "excel", "regression")
    write_task(root / "protected" / "hidden.jsonl", "excel-hidden", "excel", "hidden", True)
    write_task(root / "splits" / "ood_transfer.jsonl", "word-ood", "word", "ood_transfer")
    return root


def test_experiment_runner_records_baseline_and_automated_e07(tmp_path: Path):
    runner = ExperimentRunner(data_root(tmp_path), tmp_path / "repo")
    e01 = runner.run("E01", DeterministicCandidateProvider(), tmp_path / "results", invocation_id="e01")
    e07 = runner.run("E07", DeterministicCandidateProvider(), tmp_path / "results", invocation_id="e07")
    assert e01.status == "completed"
    assert e07.status == "completed"
    summary = json.loads((tmp_path / "results" / "E07" / "e07" / "summary.json").read_text())
    assert summary["metrics"]["comparison_label"] == "automated_cross_evaluation"


def test_experiment_runner_refuses_existing_invocation(tmp_path: Path):
    runner = ExperimentRunner(data_root(tmp_path), tmp_path / "repo")
    runner.run("E01", DeterministicCandidateProvider(), tmp_path / "results", invocation_id="same")
    try:
        runner.run("E01", DeterministicCandidateProvider(), tmp_path / "results", invocation_id="same")
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing invocation must not be overwritten")
