"""Exclusive, checksummed evidence bundles with portable internal references.

Only explicitly supplied files are copied. Arbitrary stdout/file bodies are
not credential-scrubbed: callers must supply already sanitized evidence.
Structured metadata rejects credential fields and credential-bearing endpoints.
"""

from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
from urllib.parse import urlsplit
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .hashing import sha256_file
from .run_contracts import ExecutionOutcome, AssessmentOutcome, ProtocolCapabilities, RunUsage


class ModelIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    model: str
    protocol: str
    endpoint: str | None = None

    @model_validator(mode="after")
    def endpoint_has_no_credentials(self):
        if self.endpoint is not None:
            parsed = urlsplit(self.endpoint)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("endpoint must be an HTTP(S) URL without credentials, query or fragment")
        return self


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: Literal["evidence-bundle-v2"] = "evidence-bundle-v2"
    run_id: str = Field(min_length=1)
    git_commit: str = Field(min_length=1)
    command: list[str]
    working_directory: str | None = None
    started_at: datetime
    ended_at: datetime
    exit_code: int | None
    identities: dict[str, str] = Field(default_factory=dict)
    model: ModelIdentity | None = None
    capabilities: list[ProtocolCapabilities] = Field(default_factory=list)
    usage: RunUsage = Field(default_factory=RunUsage)
    execution: ExecutionOutcome | None = None
    assessment: AssessmentOutcome | None = None
    configuration: dict = Field(default_factory=dict)
    files: dict[str, Path]

    @model_validator(mode="after")
    def times_are_ordered(self):
        if self.started_at.utcoffset() is None or self.ended_at.utcoffset() is None:
            raise ValueError("evidence timestamps must include a timezone")
        if self.ended_at < self.started_at:
            raise ValueError("evidence end precedes start")
        return self


class FileEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class EvidenceManifest(EvidenceRecord):
    files: dict[str, FileEvidence]


def _relative(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("evidence path must be relative POSIX")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in {"", ".", ".."} for p in value.split("/")):
        raise ValueError("evidence path escapes its bundle")
    return path


def _no_links(path: Path) -> Path:
    # Inspect before resolving, including parent components and Windows junctions.
    path = path.absolute()
    for current in [*reversed(path.parents), path]:
        if current.exists() or current.is_symlink():
            info = current.lstat()
            if current.is_symlink() or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise ValueError("symlink/reparse points are not allowed in evidence paths")
    return path


def _safe_metadata(value):
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in {"authorization", "proxy_authorization", "api_key", "api_key_value", "access_token", "password", "secret"}:
                raise ValueError("credential fields are forbidden in evidence metadata")
            _safe_metadata(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _safe_metadata(item)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite evidence metadata is forbidden")
    elif isinstance(value, str):
        if re.search(r"\bbearer\s+\S+", value, flags=re.I):
            raise ValueError("authorization values are forbidden in evidence metadata")
        if value.startswith(("https://", "http://")):
            parsed = urlsplit(value)
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("credential-capable URLs are forbidden in evidence metadata")


def write_evidence_bundle(root: Path, record: dict) -> Path:
    """Create a new bundle; references are relative to its manifest, never cwd."""
    root = _no_links(Path(root))
    if root.exists():
        raise FileExistsError(root)
    _safe_metadata(record)
    validated = EvidenceRecord.model_validate(record)
    sources = []
    destinations = []
    for label, raw in validated.files.items():
        relative = _relative(label)
        source = _no_links(raw)
        if not source.is_file():
            raise ValueError("missing evidence source")
        destination = PurePosixPath("files") / relative
        sources.append((label, source, destination))
        destinations.append(destination)
    if len({str(path).casefold() for path in destinations}) != len(destinations):
        raise ValueError("evidence paths collide")
    if any(a in b.parents or b in a.parents for i, a in enumerate(destinations) for b in destinations[i + 1:]):
        raise ValueError("evidence file/directory paths collide")
    # Validation completes before any output is created. Failed attempts are retained.
    root.mkdir(parents=True, exist_ok=False)
    files = {}
    for label, source, relative in sources:
        before = sha256_file(source)
        target = root.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if sha256_file(source) != before or sha256_file(target) != before:
            raise ValueError("evidence integrity changed during copy")
        files[label] = {"path": relative.as_posix(), "sha256": before, "size_bytes": target.stat().st_size}
    payload = validated.model_dump(mode="json", exclude={"files"})
    payload["files"] = files
    manifest = root / "manifest.json"
    with manifest.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    return manifest


def verify_evidence_bundle(manifest: Path) -> dict[str, Path]:
    manifest = _no_links(Path(manifest))
    content = manifest.read_text(encoding="utf-8")
    payload = json.loads(content)
    _safe_metadata(payload)
    validated = EvidenceManifest.model_validate_json(content)
    root = manifest.parent.resolve()
    resolved = {}
    for label, ref in validated.files.items():
        _relative(label)
        relative = _relative(ref.path)
        path = _no_links(root.joinpath(*relative.parts))
        if not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError("missing or external evidence file")
        if sha256_file(path) != ref.sha256 or path.stat().st_size != ref.size_bytes:
            raise ValueError("evidence integrity mismatch")
        resolved[label] = path
    return resolved
