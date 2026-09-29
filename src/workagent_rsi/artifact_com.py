"""COM checks of immutable artifact references, with suffixed disposable copies."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from . import office_capabilities
from .hashing import sha256_file
from .office_checks import EXPECTED_SUFFIXES, MEDIA_TYPES


def verify_stored_office_artifacts(artifacts: list[dict], domain: str, root: Path, *, verify=None) -> dict:
    """Keep the store immutable and verify exactly the bytes named by each ref."""
    verify = verify or office_capabilities.verify_artifact_with_com
    checks = []
    type_ok = bool(artifacts)
    for ref in artifacts:
        source = Path(ref["path"])
        digest = ref.get("sha256")
        row = {"artifact_sha256": digest}
        try:
            if ref.get("media_type") != MEDIA_TYPES.get(domain) or sha256_file(source) != digest:
                type_ok = False
                raise ValueError("artifact media type or SHA-256 does not match trusted reference")
            with tempfile.TemporaryDirectory(prefix="com-reopen-", dir=root) as temporary:
                target = Path(temporary) / ("artifact" + EXPECTED_SUFFIXES[domain])
                target.write_bytes(source.read_bytes())
                if sha256_file(target) != digest:
                    raise ValueError("COM input copy SHA-256 mismatch")
                row.update(verify(target, domain))
                if sha256_file(target) != digest or sha256_file(source) != digest:
                    raise ValueError("artifact changed during read-only COM verification")
        except OSError as exc:
            row.update(ok=False, status="unavailable", error=str(exc))
        except Exception as exc:
            row.update(ok=False, status="failed", error=str(exc))
        checks.append(row)
    ok = bool(checks) and all(row.get("ok") is True for row in checks)
    failed = next((row for row in checks if row.get("ok") is not True), {})
    result = {"ok": ok, "status": "available" if ok else failed.get("status", "failed"),
              "artifact_type_ok": type_ok, "artifacts": checks}
    if not ok:
        result["error"] = failed.get("error", "no artifacts to verify")
    versions = {row.get("version") for row in checks if row.get("version")}
    if len(versions) == 1:
        result["version"] = versions.pop()
    return result


def persist_com_result(root: Path, result: dict) -> None:
    (root / "com_reopen.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
