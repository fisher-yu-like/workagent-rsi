"""Capability and real Office-package checks used by explicit providers."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CapabilityStatus = Literal["available", "unavailable", "not_claimed"]
CommandLookup = Callable[[str], str | None]
ComProbe = Callable[[str], str | None]


class Capability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: CapabilityStatus
    version: str | None = None
    source: str | None = None
    error: str | None = None


class CapabilityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    platform: str
    capabilities: dict[str, Capability]

    def is_available(self, name: str) -> bool:
        item = self.capabilities.get(name)
        return item is not None and item.status == "available"

    @classmethod
    def for_testing(
        cls,
        *,
        word_com: str | None = "16.0",
        excel_com: str | None = "16.0",
        powerpoint_com: str | None = "16.0",
        libreoffice: str | None = "24.2",
    ) -> "CapabilityReport":
        values = {
            "word_com": word_com,
            "excel_com": excel_com,
            "powerpoint_com": powerpoint_com,
            "libreoffice": libreoffice,
        }
        capabilities = {
            name: Capability(
                name=name,
                status="available" if version else "unavailable",
                version=version,
                source="test",
                error=None if version else "not available in test fixture",
            )
            for name, version in values.items()
        }
        capabilities["external_workagent"] = Capability(
            name="external_workagent",
            status="not_claimed",
            source="project policy",
            error="no endpoint configured",
        )
        return cls(platform="test", capabilities=capabilities)


def _default_com_probe(progid: str) -> str | None:
    """Unconfigured host COM is not a controlled worker capability.

    Do not activate an application merely to probe it: PowerPoint can attach to
    a user's existing instance. Explicit worker probes can still be injected.
    """
    return None


def probe_capabilities(
    *,
    command_lookup: CommandLookup = shutil.which,
    com_probe: ComProbe = _default_com_probe,
    platform_name: str | None = None,
) -> CapabilityReport:
    capabilities: dict[str, Capability] = {}
    for name, progid in (
        ("word_com", "Word.Application"),
        ("excel_com", "Excel.Application"),
        ("powerpoint_com", "PowerPoint.Application"),
    ):
        try:
            version = com_probe(progid)
            capabilities[name] = Capability(
                name=name,
                status="available" if version else "unavailable",
                version=version,
                source=f"COM:{progid}",
                error=None if version else "isolated COM worker is not configured or its probe is unavailable",
            )
        except Exception as exc:
            capabilities[name] = Capability(
                name=name,
                status="unavailable",
                source=f"COM:{progid}",
                error=str(exc),
            )

    libreoffice_path = command_lookup("soffice") or command_lookup("libreoffice")
    capabilities["libreoffice"] = Capability(
        name="libreoffice",
        status="available" if libreoffice_path else "unavailable",
        version=None,
        source=libreoffice_path or "PATH",
        error=None if libreoffice_path else "soffice/libreoffice was not found on PATH",
    )
    capabilities["local_python_office"] = Capability(
        name="local_python_office",
        status="available",
        version="openpyxl/python-docx/python-pptx",
        source="installed Python packages",
    )
    capabilities["external_workagent"] = Capability(
        name="external_workagent",
        status="not_claimed",
        source="project policy",
        error="no endpoint or credentials configured",
    )
    return CapabilityReport(platform=platform_name or platform.platform(), capabilities=capabilities)


def verify_artifact_with_com(path: str | Path, domain: str, *, timeout_seconds: int = 60, worker=None) -> dict[str, object]:
    """Reopen a verified copy only through an explicitly isolated COM worker.

    A successful reopen is not formula recalculation or visual qualification.
    There is deliberately no host-COM fallback and no process-name cleanup.
    """
    if worker is None:
        return {"ok": False, "status": "unavailable", "error": "isolated Office COM worker is not configured",
                "capability_scope": "com_reopen", "formula_recalculation": "not_claimed", "visual_validation": "not_claimed"}
    import tempfile
    from .view_safety import ordinary_file
    from .hashing import sha256_file
    try:
        source = ordinary_file(Path(path))
        suffix = {"excel": ".xlsx", "word": ".docx", "powerpoint": ".pptx"}.get(domain)
        if suffix is None or source.suffix.lower()!=suffix:
            raise ValueError("unsupported COM artifact format")
        digest = sha256_file(source)
        with tempfile.TemporaryDirectory(prefix="office-readonly-copy-") as temporary:
            target = Path(temporary)/("artifact"+suffix)
            shutil.copyfile(source, target)
            if sha256_file(target)!=digest or sha256_file(source)!=digest:
                raise ValueError("COM copy identity changed")
            result = worker.reopen(target, domain, artifact_sha256=digest, timeout_seconds=timeout_seconds)
            if sha256_file(source)!=digest or sha256_file(target)!=digest:
                raise ValueError("Office worker modified source/copy")
            required = {"read_only": True, "macros_disabled": True, "external_updates_disabled": True, "owned_cleanup": True}
            if result.get("ok") is True and (result.get("isolation_status")!="available" or not result.get("worker_identity")
                                             or result.get("policy")!=required):
                raise ValueError("COM worker did not establish isolation/load/cleanup policy")
        return {**result, "capability_scope": "com_reopen", "formula_recalculation": "not_claimed", "visual_validation": "not_claimed"}
    except (OSError, ValueError, TypeError) as exc:
        return {"ok": False, "status": "failed", "error": str(exc), "capability_scope": "com_reopen"}


__all__ = ["Capability", "CapabilityReport", "probe_capabilities", "verify_artifact_with_com"]
