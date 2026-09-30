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
    script = r'''
$ErrorActionPreference = "Stop"
$processName = switch -Regex ($env:WORKAGENT_PROGID) {
  "Word" { "WINWORD"; break }
  "Excel" { "EXCEL"; break }
  "PowerPoint" { "POWERPNT"; break }
  default { $null }
}
$existingProcessIds = @()
if ($processName) { $existingProcessIds = @(Get-Process -Name $processName -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id) }
$app = $null
try {
  $app = New-Object -ComObject $env:WORKAGENT_PROGID
  [string]$app.Version
} finally {
  if ($app -ne $null) {
    try { $app.Quit() } catch {}
    try { [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($app) | Out-Null } catch {}
    $app = $null
  }
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
  if ($processName) {
    Get-Process -Name $processName -ErrorAction SilentlyContinue |
      Where-Object { $existingProcessIds -notcontains $_.Id } |
      Stop-Process -Force -ErrorAction SilentlyContinue
  }
}
'''
    env = os.environ.copy()
    env["WORKAGENT_PROGID"] = progid
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=env,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


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
                error=None if version else "COM application could not be created",
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


_COM_VERIFY_SCRIPT = r'''
$ErrorActionPreference = "Stop"
$path = $env:WORKAGENT_ARTIFACT
$domain = $env:WORKAGENT_DOMAIN
$processName = switch ($domain) {
  "word" { "WINWORD"; break }
  "excel" { "EXCEL"; break }
  "powerpoint" { "POWERPNT"; break }
  default { $null }
}
$existingProcessIds = @()
if ($processName) { $existingProcessIds = @(Get-Process -Name $processName -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id) }
$app = $null
$document = $null
$phase = "dispatch"
try {
  switch ($domain) {
    "word" {
      $phase = "activation"
      $app = New-Object -ComObject Word.Application
      $app.Visible = $false
      $app.DisplayAlerts = 0
      $phase = "document_open"
      $document = $app.Documents.Open($path, $false, $true, $false)
    }
    "excel" {
      $phase = "activation"
      $app = New-Object -ComObject Excel.Application
      $app.Visible = $false
      $app.DisplayAlerts = $false
      $phase = "document_open"
      $document = $app.Workbooks.Open($path, $null, $true)
    }
    "powerpoint" {
      $phase = "activation"
      $app = New-Object -ComObject PowerPoint.Application
      $phase = "document_open"
      $document = $app.Presentations.Open($path, $true, $true, $false)
    }
    default { throw "unsupported Office domain: $domain" }
  }
  @{ ok = $true; version = [string]$app.Version } | ConvertTo-Json -Compress
} catch {
  @{ ok = $false; phase = $phase; error = $_.Exception.Message } | ConvertTo-Json -Compress
  exit 1
} finally {
  if ($document -ne $null) {
    try { if ($domain -eq "powerpoint") { $document.Close() } else { $document.Close($false) } } catch {}
    try { [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) | Out-Null } catch {}
    $document = $null
  }
  if ($app -ne $null) {
    if ($domain -eq "excel") { try { $app.Workbooks.Close() } catch {} }
    try { $app.Quit() } catch {}
    try { [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($app) | Out-Null } catch {}
    $app = $null
  }
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
  if ($processName) {
    Get-Process -Name $processName -ErrorAction SilentlyContinue |
      Where-Object { $existingProcessIds -notcontains $_.Id } |
      Stop-Process -Force -ErrorAction SilentlyContinue
  }
}
'''


_COM_ACTIVATION_ERROR_MARKERS = (
    "class not registered",
    "80040154",
    "retrieving the com class factory",
    "cannot create activex component",
    "active object cannot be created",
    "activation server",
    "server execution failed",
    "80080005",
)


def _is_com_activation_failure(*diagnostics: str) -> bool:
    text = " ".join(value for value in diagnostics if value).casefold()
    return any(marker in text for marker in _COM_ACTIVATION_ERROR_MARKERS)


def _com_failure_status(payload: object, *diagnostics: str) -> str:
    phase = payload.get("phase") if isinstance(payload, dict) else None
    normalized_phase = str(phase or "").strip().casefold()
    if normalized_phase in {"document_open", "document-open", "open"}:
        return "failed"
    if normalized_phase in {"activation", "application_activation", "application-activation"}:
        return "unavailable"
    return "unavailable" if _is_com_activation_failure(*diagnostics) else "failed"


def verify_artifact_with_com(path: str | Path, domain: str, *, timeout_seconds: int = 60) -> dict[str, object]:
    env = os.environ.copy()
    env["WORKAGENT_ARTIFACT"] = str(Path(path).resolve())
    env["WORKAGENT_DOMAIN"] = domain.lower()
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _COM_VERIFY_SCRIPT],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=env,
        )
    except FileNotFoundError as exc:
        return {"ok": False, "status": "unavailable", "error": str(exc)}
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "status": "timeout", "error": f"COM verification timed out after {exc.timeout}s"}
    output = completed.stdout.strip().splitlines()
    if not output:
        error = completed.stderr.strip() or "COM verification returned no output"
        status = _com_failure_status({}, error)
        return {"ok": False, "status": status, "error": error}
    try:
        import json

        payload = json.loads(output[-1])
    except (ValueError, TypeError) as exc:
        return {"ok": False, "status": "failed", "error": f"invalid COM verification output: {exc}"}
    if completed.returncode != 0 or not payload.get("ok"):
        error = str(payload.get("error") or completed.stderr.strip() or "COM verification failed")
        status = _com_failure_status(payload, error, completed.stderr.strip())
        return {"ok": False, "status": status, "error": error}
    return {"ok": True, "status": "available", "version": payload.get("version")}


__all__ = ["Capability", "CapabilityReport", "probe_capabilities", "verify_artifact_with_com"]
