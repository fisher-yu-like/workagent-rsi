from __future__ import annotations

import importlib.util
import hashlib
import io
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = ROOT / "project_artifacts" / "phase3_experiments" / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_external_manifest_is_metadata_only_and_has_official_sources():
    manifest = json.loads((ROOT / "project_artifacts" / "phase3_experiments" / "data" / "external" / "source_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "metadata_only"
    assert manifest["policy"]["download_requires_data_license"] is True
    assert all(item["official_repository"].startswith("https://") for item in manifest["candidates"])
    assert all(item["download_status"] == "metadata_only" for item in manifest["candidates"])
    spreadsheet = next(item for item in manifest["candidates"] if item["id"] == "spreadsheetbench-v1")
    assert spreadsheet["data_url"].startswith("https://raw.githubusercontent.com/")


def test_external_intake_refuses_download_without_verified_license(tmp_path: Path):
    fetch = _load_script("fetch_external_data.py")
    with pytest.raises(PermissionError, match="license_confirmed"):
        fetch.intake(output_root=tmp_path, download=True)
    report = fetch.intake(output_root=tmp_path)
    assert report["metadata_only"] is True
    assert (tmp_path / "intake_report.json").exists()


def test_external_quality_checker_passes_without_external_files():
    quality = _load_script("quality_check_external.py")
    payload = json.loads((quality.MANIFEST).read_text(encoding="utf-8"))
    checks, failures = quality.check_manifest(payload)
    assert failures == []
    assert all(item["passed"] for item in checks)


def test_verified_archive_download_is_checksum_checked_and_recorded(tmp_path: Path):
    fetch = _load_script("fetch_external_data.py")
    content = b"approved archive bytes"
    checksum = hashlib.sha256(content).hexdigest()
    manifest = {
        "manifest_version": "test",
        "policy": {"download_requires_data_license": True},
        "candidates": [
            {
                "id": "verified-fixture",
                "license_status": "verified",
                "data_license": "CC-BY-SA-4.0",
                "checksum": checksum,
                "data_url": "https://official.example/archive.tar.gz",
                "download_status": "metadata_only",
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    report = fetch.download_candidate(
        manifest_path=manifest_path,
        candidate_id="verified-fixture",
        output_root=tmp_path / "external",
        license_confirmed=True,
        opener=lambda _url: io.BytesIO(content),
    )
    archive = tmp_path / "external" / "raw" / "verified-fixture.tar.gz"
    assert report["status"] == "admitted"
    assert report["sha256"] == checksum
    assert archive.read_bytes() == content
    assert (tmp_path / "external" / "raw" / "verified-fixture.json").exists()


def test_verified_archive_download_rejects_checksum_mismatch(tmp_path: Path):
    fetch = _load_script("fetch_external_data.py")
    manifest = {
        "manifest_version": "test",
        "policy": {"download_requires_data_license": True},
        "candidates": [
            {
                "id": "verified-fixture",
                "license_status": "verified",
                "data_license": "CC-BY-SA-4.0",
                "checksum": "a" * 64,
                "data_url": "https://official.example/archive.tar.gz",
                "download_status": "metadata_only",
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        fetch.download_candidate(
            manifest_path=manifest_path,
            candidate_id="verified-fixture",
            output_root=tmp_path / "external",
            license_confirmed=True,
            opener=lambda _url: io.BytesIO(b"wrong bytes"),
        )
    assert not list((tmp_path / "external" / "raw").glob("*.tar.gz"))
