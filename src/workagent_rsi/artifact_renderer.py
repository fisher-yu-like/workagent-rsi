"""Read-only Office rendering with page-to-artifact mappings and explicit capability status."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .hashing import canonical_json_hash, sha256_file


class RenderedPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    image_id: str
    path: str
    sha256: str
    page: int = Field(ge=1)
    artifact_location: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class RenderResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["available", "unavailable", "error", "timeout"]
    artifact_sha256: str
    renderer_identity: str
    pages: list[RenderedPage] = Field(default_factory=list)
    elapsed_seconds: float = Field(ge=0)
    error: str | None = None
    environment: dict[str, str | int | None] = Field(default_factory=dict)


_EXPORT_PDF = r'''
$ErrorActionPreference = "Stop"
$path = $env:ASSESS_ARTIFACT
$domain = $env:ASSESS_DOMAIN
$pdf = $env:ASSESS_PDF
$processName = switch ($domain) { "word" { "WINWORD" } "excel" { "EXCEL" } "powerpoint" { "POWERPNT" } }
$existing = @()
if ($processName) { $existing = @(Get-Process -Name $processName -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id) }
$app = $null
$file = $null
try {
  switch ($domain) {
    "word" {
      $app = New-Object -ComObject Word.Application
      $app.Visible = $false; $app.DisplayAlerts = 0
      $file = $app.Documents.Open($path, $false, $true, $false)
      $file.ExportAsFixedFormat($pdf, 17)
    }
    "excel" {
      $app = New-Object -ComObject Excel.Application
      $app.Visible = $false; $app.DisplayAlerts = $false
      $file = $app.Workbooks.Open($path, $null, $true)
      $file.ExportAsFixedFormat(0, $pdf)
    }
    "powerpoint" {
      $app = New-Object -ComObject PowerPoint.Application
      $file = $app.Presentations.Open($path, $true, $true, $false)
      $file.SaveAs($pdf, 32)
    }
  }
  @{ ok = $true; version = [string]$app.Version } | ConvertTo-Json -Compress
} catch {
  @{ ok = $false; error = $_.Exception.Message } | ConvertTo-Json -Compress
  exit 1
} finally {
  if ($file -ne $null) {
    try { if ($domain -eq "powerpoint") { $file.Close() } else { $file.Close($false) } } catch {}
    try { [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($file) | Out-Null } catch {}
  }
  if ($app -ne $null) {
    try { $app.Quit() } catch {}
    try { [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($app) | Out-Null } catch {}
  }
  [GC]::Collect(); [GC]::WaitForPendingFinalizers()
  if ($processName) {
    Get-Process -Name $processName -ErrorAction SilentlyContinue |
      Where-Object { $existing -notcontains $_.Id } |
      Stop-Process -Force -ErrorAction SilentlyContinue
  }
}
'''


class OfficeArtifactRenderer:
    """Render unchanged Office files to PNG via Office PDF export and Poppler."""

    def __init__(self, output_root: str | Path, *, dpi: int = 144, timeout_seconds: int = 90,
                 powershell: str = "powershell.exe", pdftoppm: str | None = None, max_pages: int = 40):
        self.output_root = Path(output_root)
        self.dpi = dpi
        self.timeout_seconds = timeout_seconds
        self.powershell = powershell
        self.pdftoppm = pdftoppm or shutil.which("pdftoppm") or "pdftoppm"
        self.max_pages = max_pages

    def identity_config(self):
        return {"renderer": "office-com-pdf-poppler-v1", "dpi": self.dpi, "max_pages": self.max_pages,
                "pdftoppm": str(Path(self.pdftoppm).resolve()) if Path(self.pdftoppm).exists() else self.pdftoppm}

    def render(self, path: str | Path, domain: str, artifact_sha256: str | None = None) -> RenderResult:
        started = time.perf_counter()
        source = Path(path).resolve()
        digest = artifact_sha256 or (sha256_file(source) if source.is_file() else canonical_json_hash({"missing": str(source)}))
        identity = canonical_json_hash(self.identity_config())
        if not source.is_file():
            return RenderResult(status="error", artifact_sha256=digest, renderer_identity=identity,
                                elapsed_seconds=time.perf_counter() - started, error="artifact missing")
        if domain not in {"excel", "word", "powerpoint"}:
            return RenderResult(status="unavailable", artifact_sha256=digest, renderer_identity=identity,
                                elapsed_seconds=time.perf_counter() - started, error="unsupported artifact domain")
        run_root = self.output_root / canonical_json_hash({"artifact": digest, **self.identity_config()})[:24]
        run_root.mkdir(parents=True, exist_ok=True)
        pdf = run_root / "rendered.pdf"
        env = {**os.environ, "ASSESS_ARTIFACT": str(source), "ASSESS_DOMAIN": domain, "ASSESS_PDF": str(pdf.resolve())}
        try:
            exported = subprocess.run([self.powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _EXPORT_PDF],
                                      env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                      timeout=self.timeout_seconds, check=False)
            lines = exported.stdout.strip().splitlines()
            payload = json.loads(lines[-1]) if lines else {}
            if exported.returncode or not payload.get("ok") or not pdf.is_file():
                return RenderResult(status="error", artifact_sha256=digest, renderer_identity=identity,
                                    elapsed_seconds=time.perf_counter() - started,
                                    error=str(payload.get("error") or exported.stderr or "Office PDF export failed"))
            prefix = run_root / "page"
            raster = subprocess.run([self.pdftoppm, "-png", "-r", str(self.dpi), str(pdf), str(prefix)],
                                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    timeout=self.timeout_seconds, check=False)
            if raster.returncode:
                return RenderResult(status="error", artifact_sha256=digest, renderer_identity=identity,
                                    elapsed_seconds=time.perf_counter() - started, error=raster.stderr or "PDF rasterization failed")
            from PIL import Image
            pages = []
            images = sorted(run_root.glob("page-*.png"), key=lambda item: int(item.stem.rsplit("-", 1)[1]))
            if len(images) > self.max_pages:
                return RenderResult(status="unavailable", artifact_sha256=digest, renderer_identity=identity,
                                    elapsed_seconds=time.perf_counter() - started,
                                    error=f"rendered {len(images)} pages, exceeding fixed max_pages={self.max_pages}")
            for number, image_path in enumerate(images, 1):
                with Image.open(image_path) as image:
                    width, height = image.size
                mapping = f"slide {number}" if domain == "powerpoint" else f"rendered page {number} ({domain} pagination)"
                pages.append(RenderedPage(image_id=f"page-{number}", path=str(image_path.resolve()), sha256=sha256_file(image_path),
                                          page=number, artifact_location=mapping, width=width, height=height))
            if not pages:
                return RenderResult(status="error", artifact_sha256=digest, renderer_identity=identity,
                                    elapsed_seconds=time.perf_counter() - started, error="renderer produced no PNG pages")
            return RenderResult(status="available", artifact_sha256=digest, renderer_identity=identity, pages=pages,
                                elapsed_seconds=time.perf_counter() - started,
                                environment={"office_version": str(payload.get("version")), "dpi": self.dpi, "page_count": len(pages)})
        except FileNotFoundError as exc:
            return RenderResult(status="unavailable", artifact_sha256=digest, renderer_identity=identity,
                                elapsed_seconds=time.perf_counter() - started, error=str(exc))
        except subprocess.TimeoutExpired as exc:
            return RenderResult(status="timeout", artifact_sha256=digest, renderer_identity=identity,
                                elapsed_seconds=time.perf_counter() - started, error=f"rendering timed out after {exc.timeout}s")
        except (ValueError, json.JSONDecodeError) as exc:
            return RenderResult(status="error", artifact_sha256=digest, renderer_identity=identity,
                                elapsed_seconds=time.perf_counter() - started, error=f"invalid renderer output: {exc}")
