"""Run the approved pilot matrix or fail closed before a formal study.

The formal path deliberately has a stronger gate than the pilot path. A project-
generated fixture can exercise the runner, but it cannot silently become a formal
benchmark merely because an experiment command was reused.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "project_artifacts" / "phase3_experiments" / "configs" / "formal_matrix.json"
MANIFEST = ROOT / "project_artifacts" / "phase3_experiments" / "data" / "external" / "source_manifest.json"
QUALITY_REPORT = ROOT / "project_artifacts" / "phase3_experiments" / "data" / "external" / "data_quality_report.json"
PILOT_DATA = ROOT / "project_artifacts" / "phase3_experiments" / "data"
sys.path.insert(0, str(ROOT / "src"))

from workagent_rsi.candidate_provider import CodexCandidateProvider, DeterministicCandidateProvider
from workagent_rsi.experiment_runner import ExperimentRunner


class FormalDataGateError(RuntimeError):
    """Raised when a formal run would use data that has not passed admission."""

    def __init__(self, reasons: list[str], report: dict[str, Any] | None = None) -> None:
        self.reasons = reasons
        self.report = report or {"ready": False, "reasons": reasons}
        super().__init__("formal data gate failed: " + "; ".join(reasons))


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_formal_gate(
    manifest_path: str | Path = MANIFEST,
    quality_report_path: str | Path = QUALITY_REPORT,
    data_root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate source admission without modifying the dataset or result tree."""

    manifest_file = Path(manifest_path)
    quality_file = Path(quality_report_path)
    reasons: list[str] = []
    if not manifest_file.exists():
        reasons.append("source manifest is missing")
        manifest: dict[str, Any] = {}
    else:
        manifest = _read_json(manifest_file)
    if not quality_file.exists():
        reasons.append("external data quality report is missing")
        quality: dict[str, Any] = {}
    else:
        quality = _read_json(quality_file)

    selected = manifest.get("formal_dataset_selected")
    if not selected:
        reasons.append("formal_dataset_selected is not set")
    if manifest.get("status") != "ready":
        reasons.append(f"source manifest status is {manifest.get('status')!r}, expected 'ready'")
    candidates = {item.get("id"): item for item in manifest.get("candidates", [])}
    candidate = candidates.get(selected) if selected else None
    if candidate is None:
        reasons.append("selected formal dataset is absent from source manifest")
    else:
        if candidate.get("license_status") != "verified":
            reasons.append("selected dataset does not have a verified data license")
        if not candidate.get("data_license"):
            reasons.append("selected dataset has no data license text")
        checksum = str(candidate.get("checksum") or "")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", checksum):
            reasons.append("selected dataset has no valid SHA-256 checksum")
        if candidate.get("download_status") not in {"admitted", "downloaded"}:
            reasons.append("selected dataset has not been admitted to the data layer")

    if quality.get("status") != "pass":
        reasons.append(f"external data quality report status is {quality.get('status')!r}")
    if selected and quality.get("formal_dataset_selected") != selected:
        reasons.append("quality report does not identify the selected formal dataset")

    root = Path(data_root) if data_root is not None else ROOT / "project_artifacts" / "phase3_experiments" / "data" / "external" / "processed"
    required = (
        root / "splits" / "evolve.jsonl",
        root / "splits" / "develop.jsonl",
        root / "splits" / "regression.jsonl",
        root / "splits" / "ood_transfer.jsonl",
        root / "protected" / "hidden.jsonl",
    )
    missing = [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]
    reasons.extend(f"missing formal split: {path}" for path in missing)

    report = {
        "ready": not reasons,
        "candidate_id": selected,
        "manifest": str(manifest_file.resolve()),
        "quality_report": str(quality_file.resolve()),
        "data_root": str(root.resolve()),
        "manifest_sha256": _sha256(manifest_file) if manifest_file.exists() else None,
        "quality_report_sha256": _sha256(quality_file) if quality_file.exists() else None,
        "required_files": [str(path.resolve()) for path in required],
        "reasons": reasons,
    }
    if reasons:
        raise FormalDataGateError(reasons, report)
    return report


def _codex_version() -> str:
    try:
        return subprocess.check_output(["codex", "--version"], text=True, stderr=subprocess.STDOUT).strip()
    except Exception:
        return "unavailable"


def _provider(name: str):
    if name == "deterministic":
        return DeterministicCandidateProvider()
    if name != "codex":
        raise ValueError(f"unknown provider: {name}")
    schema = ROOT / "project_artifacts" / "phase3_experiments" / "provider" / "candidate_patch.schema.json"
    return CodexCandidateProvider(
        schema_path=schema,
        provider_version=_codex_version(),
        timeout_seconds=180,
        extra_args=["--ignore-user-config", "--oss", "--local-provider", "ollama", "--model", "qwen2.5:7b"],
        model_identity="ollama:qwen2.5:7b",
    )


def _load_matrix(path: str | Path = CONFIG) -> dict[str, Any]:
    matrix = _read_json(path)
    if matrix.get("matrix_version") != "formal-matrix-v0.1.0":
        raise ValueError("unsupported formal matrix version")
    return matrix


def run_matrix(
    *,
    mode: str,
    provider_name: str,
    experiments: list[str] | None = None,
    output_root: str | Path | None = None,
    invocation_id: str | None = None,
    config_path: str | Path = CONFIG,
    manifest_path: str | Path = MANIFEST,
    quality_report_path: str | Path = QUALITY_REPORT,
    data_root: str | Path | None = None,
) -> dict[str, Any]:
    matrix = _load_matrix(config_path)
    if mode not in {"pilot", "formal"}:
        raise ValueError("mode must be 'pilot' or 'formal'")
    defaults = matrix[mode]["experiments"]
    selected_experiments = experiments or list(defaults)
    invalid = sorted(set(selected_experiments) - set(defaults))
    if invalid:
        raise ValueError(f"experiments are not in {mode} matrix: {invalid}")

    gate: dict[str, Any] | None = None
    if mode == "formal":
        gate = validate_formal_gate(manifest_path, quality_report_path, data_root or ROOT / matrix["dataset"]["formal_data_root"])
        selected_data_root = Path(data_root or ROOT / matrix["dataset"]["formal_data_root"])
    else:
        selected_data_root = Path(data_root or ROOT / matrix["pilot"]["data_root"])

    invocation = invocation_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    default_output = ROOT / "project_artifacts" / "results" / "formal"
    if mode == "pilot":
        default_output = ROOT / "project_artifacts" / "results" / "qualification" / "formal-pilot"
    base_output = Path(output_root) if output_root is not None else default_output
    invocation_root = base_output / invocation
    invocation_root.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(timezone.utc)
    provider = _provider(provider_name)
    runner = ExperimentRunner(selected_data_root, ROOT)
    rows = []
    for experiment_id in selected_experiments:
        result = runner.run(
            experiment_id,
            provider,
            invocation_root,
            invocation_id=experiment_id.lower(),
            rounds=6,
        )
        rows.append(result.model_dump(mode="json"))

    summary = {
        "mode": mode,
        "provider": provider_name,
        "invocation_id": invocation,
        "dataset_kind": "external-admitted" if mode == "formal" else "project-generated",
        "formal_gate": gate,
        "claim_boundary": {
            "external_benchmark": mode == "formal",
            "formal_main_study": mode == "formal",
            "manual_annotation": False,
            "unavailable_is_not_a_score": True,
        },
        "experiments": rows,
        "started_at": started_at.isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    }
    (invocation_root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (invocation_root / "run_scope.md").write_text(
        f"# {mode.title()} experiment scope\n\n"
        f"Dataset kind: `{summary['dataset_kind']}`. Provider: `{provider_name}`. "
        "Metrics are populated only from the recorded experiment outputs; unavailable channels are not converted to scores.\n",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the guarded pilot/formal WorkAgent-RSI experiment matrix")
    parser.add_argument("--mode", choices=("pilot", "formal"), default="formal")
    parser.add_argument("--provider", choices=("deterministic", "codex"), default="codex")
    parser.add_argument("--experiments", default=None, help="comma-separated subset of the configured matrix")
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--invocation-id", default=None)
    args = parser.parse_args(argv)
    experiments = [item.strip() for item in args.experiments.split(",") if item.strip()] if args.experiments else None
    try:
        summary = run_matrix(mode=args.mode, provider_name=args.provider, experiments=experiments, output_root=args.output_root, invocation_id=args.invocation_id)
    except FormalDataGateError as exc:
        print(json.dumps(exc.report, indent=2, sort_keys=True))
        return 2
    print(json.dumps({"mode": summary["mode"], "invocation_id": summary["invocation_id"], "experiment_count": len(summary["experiments"])}, sort_keys=True))
    return 0 if all(row["status"] == "completed" for row in summary["experiments"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
