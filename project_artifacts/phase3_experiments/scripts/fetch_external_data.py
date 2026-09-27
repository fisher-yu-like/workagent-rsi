"""External dataset intake with a fail-closed, checksum-verified download gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, BinaryIO
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "project_artifacts" / "phase3_experiments" / "data" / "external" / "source_manifest.json"


def load_manifest(path: str | Path = MANIFEST) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("policy", {}).get("download_requires_data_license") is not True:
        raise ValueError("external intake policy must require a data license")
    return payload


def intake(*, manifest_path: str | Path = MANIFEST, output_root: str | Path | None = None, download: bool = False, license_confirmed: bool = False) -> dict:
    payload = load_manifest(manifest_path)
    if download and not license_confirmed:
        raise PermissionError("download requires explicit license_confirmed=True")
    eligible = [
        item for item in payload.get("candidates", [])
        if item.get("license_status") == "verified"
        and item.get("data_license")
        and item.get("checksum")
    ]
    if download and not eligible:
        raise PermissionError("no candidate has a verified data license and checksum")
    result = {
        "status": "download_not_requested" if not download else "download_allowed",
        "metadata_only": not download,
        "eligible_candidates": [item["id"] for item in eligible],
        "candidate_count": len(payload.get("candidates", [])),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(Path(manifest_path).resolve()),
    }
    if output_root is not None:
        root = Path(output_root)
        root.mkdir(parents=True, exist_ok=True)
        (root / "intake_report.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def download_candidate(
    *,
    manifest_path: str | Path = MANIFEST,
    candidate_id: str,
    output_root: str | Path,
    license_confirmed: bool,
    opener: Callable[[str], BinaryIO] = urlopen,
) -> dict:
    """Download one admitted archive to ``raw/`` and verify it before rename.

    The function never extracts or transforms an archive. This keeps the raw
    source immutable and leaves schema/leakage processing to a later gate.
    ``opener`` is injectable only for deterministic tests; production uses
    ``urllib`` and therefore the manifest's HTTPS URL.
    """

    payload = load_manifest(manifest_path)
    if not license_confirmed:
        raise PermissionError("download requires explicit license_confirmed=True")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", candidate_id):
        raise ValueError("candidate_id contains unsafe path characters")
    candidate = next((item for item in payload.get("candidates", []) if item.get("id") == candidate_id), None)
    if candidate is None:
        raise KeyError(f"unknown candidate: {candidate_id}")
    if candidate.get("license_status") != "verified" or not candidate.get("data_license"):
        raise PermissionError("candidate data license is not verified")
    expected = str(candidate.get("checksum") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise PermissionError("candidate needs a valid SHA-256 checksum before download")
    source_url = str(candidate.get("data_url") or "")
    if not source_url.startswith("https://"):
        raise PermissionError("candidate data_url must be an official HTTPS URL")

    raw_root = Path(output_root).resolve() / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)
    archive = raw_root / f"{candidate_id}.tar.gz"
    temporary = archive.with_name(archive.name + ".part")
    digest = hashlib.sha256()
    size = 0
    response = opener(source_url)
    try:
        with temporary.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                digest.update(chunk)
                size += len(chunk)
    finally:
        close = getattr(response, "close", None)
        if close is not None:
            close()
    actual = digest.hexdigest()
    if actual != expected:
        temporary.unlink(missing_ok=True)
        raise ValueError(f"archive checksum mismatch: expected {expected}, got {actual}")
    temporary.replace(archive)
    result = {
        "status": "admitted",
        "candidate_id": candidate_id,
        "source_url": source_url,
        "license_status": candidate["license_status"],
        "data_license": candidate["data_license"],
        "sha256": actual,
        "size_bytes": size,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "archive": str(archive.resolve()),
    }
    (raw_root / f"{candidate_id}.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record external dataset metadata or download an explicitly admitted archive")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--output-root", type=Path, default=ROOT / "project_artifacts" / "results" / "qualification" / "external-data")
    parser.add_argument("--download", action="store_true", help="requires --license-confirmed and a verified manifest entry")
    parser.add_argument("--candidate-id", help="candidate to download when --download is set")
    parser.add_argument("--license-confirmed", action="store_true")
    args = parser.parse_args(argv)
    if args.download:
        if not args.candidate_id:
            parser.error("--candidate-id is required with --download")
        result = download_candidate(
            manifest_path=args.manifest,
            candidate_id=args.candidate_id,
            output_root=args.output_root,
            license_confirmed=args.license_confirmed,
        )
    else:
        result = intake(manifest_path=args.manifest, output_root=args.output_root, download=False, license_confirmed=False)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
