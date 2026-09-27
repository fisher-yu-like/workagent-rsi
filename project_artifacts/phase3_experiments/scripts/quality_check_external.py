"""Validate the external metadata/license gate and protected data boundary."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = ROOT / "project_artifacts" / "phase3_experiments" / "data" / "external"
MANIFEST = DATA_ROOT / "source_manifest.json"
REPORT = DATA_ROOT / "data_quality_report.json"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_manifest(payload: dict) -> tuple[list[dict], list[str]]:
    checks: list[dict] = []
    failures: list[str] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            failures.append(f"{name}: {detail}")

    candidates = payload.get("candidates", [])
    check("manifest_version", bool(payload.get("manifest_version")), "missing manifest_version")
    check("metadata_only", payload.get("status") == "metadata_only", f"status={payload.get('status')}")
    check("candidate_count", len(candidates) >= 1, f"count={len(candidates)}")
    ids = [item.get("id") for item in candidates]
    check("unique_ids", len(ids) == len(set(ids)), "duplicate candidate ids")
    for item in candidates:
        required = {"id", "name", "official_repository", "version", "license_status", "download_status", "leakage_risks"}
        missing = sorted(required - set(item))
        check(f"schema:{item.get('id')}", not missing, f"missing={missing}")
        check(f"official_url:{item.get('id')}", str(item.get("official_repository", "")).startswith("https://"), "official repository URL is not HTTPS")
        check(f"download_boundary:{item.get('id')}", item.get("download_status") == "metadata_only", f"download_status={item.get('download_status')}")
        if item.get("license_status") not in {"verified", "conditional_verified"}:
            check(f"unverified_no_checksum:{item.get('id')}", item.get("checksum") in {None, ""}, "unverified candidate has a checksum")
    return checks, failures


def main() -> int:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    checks, failures = check_manifest(payload)
    forbidden_files = [
        str(path.relative_to(DATA_ROOT)).replace("\\", "/")
        for layer in ("raw", "interim", "processed", "public", "protected")
        for path in (DATA_ROOT / layer).rglob("*")
        if path.is_file()
    ] if any((DATA_ROOT / layer).exists() for layer in ("raw", "interim", "processed", "public", "protected")) else []
    checks.append({"name": "no_external_files_before_license", "passed": not forbidden_files, "detail": str(forbidden_files)})
    if forbidden_files:
        failures.append(f"no_external_files_before_license: {forbidden_files}")
    report = {
        "status": "pass" if not failures else "fail",
        "mode": "metadata_only",
        "manifest_sha256": _hash(MANIFEST),
        "candidate_count": len(payload.get("candidates", [])),
        "checks": checks,
        "failures": failures,
        "formal_dataset_selected": payload.get("formal_dataset_selected"),
    }
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
