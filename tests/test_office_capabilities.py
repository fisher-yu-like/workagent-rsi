from __future__ import annotations

import json
import os
import subprocess

import pytest
from openpyxl import Workbook

from workagent_rsi.office_capabilities import CapabilityReport, probe_capabilities
from workagent_rsi.run import Run


def _automation_process_ids(name: str) -> set[int]:
    if os.name != "nt":
        return set()
    command = (
        f"@(Get-CimInstance Win32_Process -Filter \"Name='{name}.EXE'\" "
        "| Where-Object { $_.CommandLine -like '* /automation*' } | Select-Object -ExpandProperty ProcessId) "
        "| ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        check=True,
    )
    value = completed.stdout.strip()
    if not value:
        return set()
    parsed = json.loads(value)
    if isinstance(parsed, list):
        return {int(item) for item in parsed}
    return {int(parsed)}


def test_probe_capabilities_separates_com_and_libreoffice():
    report = probe_capabilities(
        command_lookup=lambda name: None if name in {"soffice", "libreoffice"} else f"C:/tools/{name}.exe",
        com_probe=lambda progid: "16.0" if progid in {"Word.Application", "Excel.Application", "PowerPoint.Application"} else None,
        platform_name="test-windows",
    )

    assert report.capabilities["word_com"].status == "available"
    assert report.capabilities["excel_com"].version == "16.0"
    assert report.capabilities["libreoffice"].status == "unavailable"
    assert report.capabilities["external_workagent"].status == "not_claimed"


def test_run_rejects_unknown_execution_provider(tmp_path):
    with pytest.raises(ValueError, match="unknown execution provider"):
        Run(tmp_path, execution_provider="unknown").execute(
            {"task_id": "bad-provider", "domain": "word", "instruction": "Create"}
        )


def test_com_provider_uses_injected_capability_report_without_reprobing(tmp_path, monkeypatch):
    report = CapabilityReport.for_testing(
        word_com=None,
        excel_com=None,
        powerpoint_com=None,
        libreoffice=None,
    )
    monkeypatch.setattr(
        "workagent_rsi.executor.probe_capabilities",
        lambda: pytest.fail("injected capability reports must be reused"),
    )

    result = Run(tmp_path, execution_provider="com", capability_report=report).execute(
        {"task_id": "no-com", "domain": "word", "instruction": "Create"}
    )

    assert result["state"] == "UNAVAILABLE"
    assert result["failure"]["status"] == "unavailable"
    assert "COM" in result["failure"]["message"]


def test_verify_artifact_with_com_classifies_activation_failure_as_unavailable(monkeypatch, tmp_path):
    from workagent_rsi import office_capabilities

    completed = subprocess.CompletedProcess(
        args=["powershell.exe"],
        returncode=1,
        stdout='{"ok":false,"error":"Retrieving the COM class factory for component with CLSID {000209FF-0000-0000-C000-000000000046} failed: 80040154 Class not registered"}\n',
        stderr="",
    )
    monkeypatch.setattr(office_capabilities.subprocess, "run", lambda *args, **kwargs: completed)

    result = office_capabilities.verify_artifact_with_com(tmp_path / "missing.docx", "word")

    assert result == {
        "ok": False,
        "status": "unavailable",
        "error": "Retrieving the COM class factory for component with CLSID {000209FF-0000-0000-C000-000000000046} failed: 80040154 Class not registered",
    }


def test_verify_artifact_with_com_keeps_document_open_failure_as_failed(monkeypatch, tmp_path):
    from workagent_rsi import office_capabilities

    completed = subprocess.CompletedProcess(
        args=["powershell.exe"],
        returncode=1,
        stdout='{"ok":false,"error":"The file is corrupted and cannot be opened by Word"}\n',
        stderr="",
    )
    monkeypatch.setattr(office_capabilities.subprocess, "run", lambda *args, **kwargs: completed)

    result = office_capabilities.verify_artifact_with_com(tmp_path / "corrupt.docx", "word")

    assert result == {
        "ok": False,
        "status": "failed",
        "error": "The file is corrupted and cannot be opened by Word",
    }


@pytest.mark.skipif(os.name != "nt", reason="requires Windows Office COM")
def test_com_reopen_does_not_leave_new_excel_automation_process(tmp_path):
    from workagent_rsi.office_capabilities import verify_artifact_with_com

    path = tmp_path / "probe.xlsx"
    workbook = Workbook()
    workbook.save(path)
    before = _automation_process_ids("EXCEL")

    result = verify_artifact_with_com(path, "excel")

    after = _automation_process_ids("EXCEL")
    assert result["ok"] is True
    assert after == before
