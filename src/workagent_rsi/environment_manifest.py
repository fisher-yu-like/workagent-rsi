"""Read-only, secret-free environment inventory for a frozen local baseline."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=repo, text=True, encoding="utf-8", errors="replace"
    ).rstrip("\r\n")


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _codex_capability() -> dict[str, object]:
    executable = shutil.which("codex")
    if executable is None:
        return {"status": "unavailable", "executable": None, "version": None}
    try:
        result = subprocess.run(
            [executable, "--version"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "version_unavailable", "executable": executable, "version": None}
    return {
        "status": "available" if result.returncode == 0 else "version_unavailable",
        "executable": executable,
        "version": result.stdout.strip() if result.returncode == 0 else None,
    }


def capture_environment(repo: Path, output: Path) -> dict[str, object]:
    """Capture local facts without contacting a model/API or reading credential values.

    COM is deliberately reported as unprobed: loading an Office application is
    a separate, process-creating capability check, not part of a read-only
    baseline inventory. The output is exclusive-create evidence.
    """
    repo = Path(repo).resolve(strict=True)
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    status = _git(repo, "status", "--porcelain=v1", "--untracked-files=normal")
    manifest: dict[str, object] = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(repo),
        "git_commit": _git(repo, "rev-parse", "HEAD"),
        "git_branch": _git(repo, "branch", "--show-current"),
        "dirty_paths": sorted(line[3:] for line in status.splitlines() if len(line) >= 4),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "dependencies": {
            name: _package_version(name)
            for name in ("pytest", "pydantic", "PyYAML", "openpyxl", "python-docx", "python-pptx")
        },
        "capabilities": {
            "codex_cli": _codex_capability(),
            "api": {
                "implemented_transport": "OpenAI-compatible chat/completions for execution and candidates; Responses for artifact judgment",
                "live_connection": "not_probed",
            },
            "office_com": {"status": "not_probed", "applications": ["Word", "Excel", "PowerPoint"]},
            "rendering": {
                "pdftoppm": shutil.which("pdftoppm"),
                "powershell": shutil.which("powershell.exe"),
                "libreoffice": shutil.which("soffice") or shutil.which("libreoffice"),
                "actual_render": "not_probed",
            },
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return manifest
