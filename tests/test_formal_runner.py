from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_runner():
    path = ROOT / "project_artifacts" / "phase3_experiments" / "scripts" / "run_formal.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest(*, selected=None, status="metadata_only", license_status="conditional_review_required"):
    return {
        "status": status,
        "formal_dataset_selected": selected,
        "candidates": [
            {
                "id": selected or "spreadsheetbench-v1",
                "license_status": license_status,
                "data_license": "CC-BY-SA-4.0" if license_status == "verified" else None,
                "checksum": "a" * 64 if license_status == "verified" else None,
                "download_status": "admitted" if license_status == "verified" else "metadata_only",
            }
        ],
    }


def test_formal_gate_rejects_unselected_external_dataset(tmp_path: Path):
    runner = _load_runner()
    manifest_path = tmp_path / "source_manifest.json"
    report_path = tmp_path / "data_quality_report.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    report_path.write_text(json.dumps({"status": "pass"}), encoding="utf-8")

    with pytest.raises(runner.FormalDataGateError, match="formal_dataset_selected"):
        runner.validate_formal_gate(manifest_path, report_path, tmp_path / "data")


def test_formal_gate_requires_admitted_files_and_quality_report(tmp_path: Path):
    runner = _load_runner()
    manifest_path = tmp_path / "source_manifest.json"
    report_path = tmp_path / "data_quality_report.json"
    data_root = tmp_path / "data"
    manifest_path.write_text(json.dumps(_manifest(selected="spreadsheetbench-v1", status="ready", license_status="verified")), encoding="utf-8")
    report_path.write_text(json.dumps({"status": "pass", "formal_dataset_selected": "spreadsheetbench-v1"}), encoding="utf-8")

    with pytest.raises(runner.FormalDataGateError, match="missing formal split"):
        runner.validate_formal_gate(manifest_path, report_path, data_root)

    for relative in ("splits/evolve.jsonl", "splits/develop.jsonl", "splits/regression.jsonl", "splits/ood_transfer.jsonl", "protected/hidden.jsonl"):
        path = data_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    gate = runner.validate_formal_gate(manifest_path, report_path, data_root)
    assert gate["ready"] is True
    assert gate["candidate_id"] == "spreadsheetbench-v1"


def test_pilot_runner_writes_results_and_labels_project_fixture(tmp_path: Path):
    runner = _load_runner()
    result = runner.run_matrix(
        mode="pilot",
        provider_name="deterministic",
        experiments=["E01"],
        output_root=tmp_path / "results",
        invocation_id="pilot-test",
    )
    assert result["mode"] == "pilot"
    assert result["claim_boundary"]["external_benchmark"] is False
    assert result["experiments"][0]["status"] == "completed"
    assert (tmp_path / "results" / "pilot-test" / "summary.json").exists()


def test_formal_matrix_and_baselines_are_explicit_about_claim_boundary():
    matrix = json.loads((ROOT / "project_artifacts" / "phase3_experiments" / "configs" / "formal_matrix.json").read_text(encoding="utf-8"))
    baselines = json.loads((ROOT / "project_artifacts" / "phase3_experiments" / "configs" / "baselines.json").read_text(encoding="utf-8"))
    assert matrix["formal"]["requires_external_gate"] is True
    assert matrix["pilot"]["dataset_kind"] == "project-generated"
    assert baselines["claim_boundary"]["manual_annotation"] is False
    assert all("metrics" not in arm for arm in baselines["arms"])


def test_analysis_excludes_unavailable_experiment_from_numeric_aggregates(tmp_path: Path):
    analysis = _load_analysis()
    (tmp_path / "pilot" / "summary.json").parent.mkdir(parents=True)
    (tmp_path / "pilot" / "summary.json").write_text(
        json.dumps(
            {
                "mode": "pilot",
                "claim_boundary": {"external_benchmark": False},
                "experiments": [
                    {"experiment_id": "E01", "status": "completed", "metrics": {"score": 1.0}},
                    {"experiment_id": "E05", "status": "unavailable", "metrics": {"score": 999.0}},
                ],
            }
        ),
        encoding="utf-8",
    )
    result = analysis.analyze_results(tmp_path)
    assert result["completed_experiments"] == 1
    assert result["unavailable_experiments"] == 1
    assert result["numeric_means"] == {"score": 1.0}
    assert result["claims_allowed"] is False


def _load_analysis():
    path = ROOT / "project_artifacts" / "phase3_experiments" / "scripts" / "analyze_formal.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
