"""Read-only, file-level checks for Excel, Word and PowerPoint artifacts."""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .contracts import TaskSpec
from .render_checks import check_powerpoint_geometry


class OfficeCheckReport(BaseModel):
    """Evidence produced by one artifact inspection.

    The report intentionally contains no candidate-workspace paths or mutable
    evaluator state.  It can be persisted as JSON next to a run result.
    """

    model_config = ConfigDict(extra="forbid")

    path: str
    domain: str
    status: str
    passed: bool
    artifact_sha256: str | None = None
    size_bytes: int = 0
    dimensions: dict[str, float] = Field(default_factory=dict)
    failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    channel_status: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def critical_failures(self) -> list[str]:
        """Compatibility name used by ``EvaluationReport`` callers."""

        return self.failures


MEDIA_TYPES = {
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "word": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "powerpoint": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
EXPECTED_SUFFIXES = {"excel": ".xlsx", "word": ".docx", "powerpoint": ".pptx"}
OOXML_MEMBERS = {
    "excel": ("[Content_Types].xml", "xl/workbook.xml"),
    "word": ("[Content_Types].xml", "word/document.xml"),
    "powerpoint": ("[Content_Types].xml", "ppt/presentation.xml"),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_value(actual: Any, expected: Any) -> bool:
    if actual == expected:
        return True
    if actual is None or expected is None:
        return False
    return str(actual).strip() == str(expected).strip()


def _cell_key(key: str, default_sheet: str | None = None) -> tuple[str, str]:
    value = str(key)
    if "!" in value:
        sheet, coordinate = value.rsplit("!", 1)
        return sheet.strip("'"), coordinate.strip()
    return default_sheet or "", value


def _ratio(total: int, passed: int) -> float:
    return 1.0 if total == 0 else round(passed / total, 6)


def _base_report(path: Path, domain: str) -> tuple[dict[str, Any], list[str], list[str], list[str], dict[str, float], dict[str, str]]:
    failures: list[str] = []
    warnings: list[str] = []
    evidence: list[str] = []
    dimensions: dict[str, float] = {
        "format_validity": 0.0,
        "marker_correctness": 0.0,
        "structure_correctness": 0.0,
    }
    channels = {"package": "unavailable", "structure": "unavailable"}
    metadata: dict[str, Any] = {}
    if not path.exists() or not path.is_file():
        failures.append(f"artifact does not exist: {path}")
        return metadata, failures, warnings, evidence, dimensions, channels

    digest = _sha256(path)
    evidence.extend([f"artifact_sha256:{digest}", f"size_bytes:{path.stat().st_size}"])
    metadata["suffix"] = path.suffix.lower()
    metadata["ooxml_members"] = []
    if path.suffix.lower() != EXPECTED_SUFFIXES.get(domain):
        failures.append(f"unexpected file suffix for {domain}: {path.suffix}")
    try:
        with zipfile.ZipFile(path) as package:
            names = set(package.namelist())
            required_members = set(OOXML_MEMBERS.get(domain, ()))
            missing = sorted(required_members - names)
            metadata["ooxml_members"] = sorted(name for name in names if name in required_members)
            if missing:
                failures.append(f"OOXML members missing: {', '.join(missing)}")
            else:
                channels["package"] = "available"
                evidence.append(f"ooxml_members:{','.join(sorted(required_members))}")
    except (OSError, zipfile.BadZipFile) as exc:
        failures.append(f"OOXML package unreadable: {exc}")
    return metadata, failures, warnings, evidence, dimensions, channels


def _excel_checks(path: Path, constraints: dict[str, Any], failures: list[str], evidence: list[str], dimensions: dict[str, float], channels: dict[str, str], metadata: dict[str, Any]) -> None:
    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=False, data_only=False)
    try:
        sheet_names = list(workbook.sheetnames)
        metadata["sheet_names"] = sheet_names
        evidence.append(f"sheet_names:{','.join(sheet_names)}")
        required_sheets = [str(item) for item in constraints.get("required_sheets", [])]
        missing_sheets = [name for name in required_sheets if name not in sheet_names]
        if missing_sheets:
            failures.append(f"required sheet(s) missing: {', '.join(missing_sheets)}")

        required_cells = constraints.get("required_cells", {})
        cell_checks = 0
        cell_passes = 0
        default_sheet = sheet_names[0] if len(sheet_names) == 1 else None
        for raw_key, expected in (required_cells.items() if isinstance(required_cells, dict) else []):
            sheet_name, coordinate = _cell_key(str(raw_key), default_sheet)
            cell_checks += 1
            if not sheet_name or sheet_name not in workbook.sheetnames:
                failures.append(f"required cell sheet missing: {raw_key}")
                continue
            actual = workbook[sheet_name][coordinate].value
            if _same_value(actual, expected):
                cell_passes += 1
            else:
                failures.append(f"cell {raw_key} expected {expected!r}, got {actual!r}")
        dimensions["cell_correctness"] = _ratio(cell_checks, cell_passes)

        formulas = constraints.get("required_formulas", {})
        formula_checks = 0
        formula_passes = 0
        for raw_key, expected in (formulas.items() if isinstance(formulas, dict) else []):
            sheet_name, coordinate = _cell_key(str(raw_key), default_sheet)
            formula_checks += 1
            if not sheet_name or sheet_name not in workbook.sheetnames:
                failures.append(f"formula sheet missing: {raw_key}")
                continue
            actual = workbook[sheet_name][coordinate].value
            if _same_value(actual, expected):
                formula_passes += 1
            else:
                failures.append(f"formula {raw_key} expected {expected!r}, got {actual!r}")
        required_values = constraints.get("required_formula_values", {})
        if isinstance(required_values, dict) and required_values:
            cached = load_workbook(path, read_only=False, data_only=True)
            try:
                for raw_key, expected in required_values.items():
                    sheet_name, coordinate = _cell_key(str(raw_key), default_sheet)
                    formula_checks += 1
                    actual = cached[sheet_name][coordinate].value if sheet_name in cached.sheetnames else None
                    if _same_value(actual, expected):
                        formula_passes += 1
                    else:
                        failures.append(f"cached formula value {raw_key} expected {expected!r}, got {actual!r}")
            finally:
                cached.close()
        dimensions["formula_correctness"] = _ratio(formula_checks, formula_passes)
        if formula_checks == 0:
            dimensions["formula_correctness"] = 1.0
        dimensions["structure_correctness"] = _ratio(1 + len(required_sheets) + cell_checks, 1 + sum(name in sheet_names for name in required_sheets) + cell_passes)
        channels["structure"] = "available"

        values = [cell.value for sheet in workbook.worksheets for row in sheet.iter_rows() for cell in row]
        marker = str(constraints.get("required_text", ""))
        marker_ok = not marker or any(marker in str(value) for value in values if value is not None)
        dimensions["marker_correctness"] = 1.0 if marker_ok else 0.0
        if not marker_ok:
            failures.append(f"required marker missing: {marker}")
    finally:
        workbook.close()


def _word_checks(path: Path, constraints: dict[str, Any], failures: list[str], evidence: list[str], dimensions: dict[str, float], channels: dict[str, str], metadata: dict[str, Any]) -> None:
    from docx import Document

    document = Document(path)
    paragraphs = list(document.paragraphs)
    headings = [paragraph for paragraph in paragraphs if paragraph.style and paragraph.style.name.lower().startswith("heading")]
    metadata["paragraph_count"] = len(paragraphs)
    metadata["heading_count"] = len(headings)
    evidence.append(f"paragraph_count:{len(paragraphs)}")
    required_headings = [str(item) for item in constraints.get("required_headings", [])]
    heading_texts = [paragraph.text.strip() for paragraph in headings]
    missing_headings = [heading for heading in required_headings if heading not in heading_texts]
    if missing_headings:
        failures.append(f"required heading(s) missing: {', '.join(missing_headings)}")
    heading_style_checks = constraints.get("required_heading_styles", {})
    style_checks = 0
    style_passes = 0
    for heading_text, expected_style in (heading_style_checks.items() if isinstance(heading_style_checks, dict) else []):
        style_checks += 1
        matches = [paragraph for paragraph in headings if paragraph.text.strip() == str(heading_text)]
        if matches and matches[0].style.name == str(expected_style):
            style_passes += 1
        else:
            failures.append(f"heading {heading_text!r} expected style {expected_style!r}")
    dimensions["style_correctness"] = _ratio(style_checks, style_passes)
    dimensions["heading_correctness"] = _ratio(len(required_headings), len(required_headings) - len(missing_headings))
    dimensions["structure_correctness"] = _ratio(1 + len(required_headings) + style_checks, 1 + len(required_headings) - len(missing_headings) + style_passes)
    channels["structure"] = "available"
    marker = str(constraints.get("required_text", ""))
    text = "\n".join(paragraph.text for paragraph in paragraphs)
    text += "\n" + "\n".join(cell.text for table in document.tables for row in table.rows for cell in row.cells)
    marker_ok = not marker or marker in text
    dimensions["marker_correctness"] = 1.0 if marker_ok else 0.0
    if not marker_ok:
        failures.append(f"required marker missing: {marker}")
    try:
        with zipfile.ZipFile(path) as package:
            styles_xml = package.read("word/styles.xml")
            metadata["styles_xml_bytes"] = len(styles_xml)
            evidence.append("ooxml_styles_read:word/styles.xml")
            dimensions["ooxml_correctness"] = 1.0
    except (KeyError, zipfile.BadZipFile) as exc:
        dimensions["ooxml_correctness"] = 0.0
        failures.append(f"Word styles OOXML unreadable: {exc}")
    warnings = constraints.get("_warnings")
    if warnings:
        evidence.extend(str(item) for item in warnings)


def _powerpoint_checks(path: Path, constraints: dict[str, Any], failures: list[str], warnings: list[str], evidence: list[str], dimensions: dict[str, float], channels: dict[str, str], metadata: dict[str, Any]) -> None:
    from pptx import Presentation

    presentation = Presentation(path)
    slide_count = len(presentation.slides)
    metadata["slide_count"] = slide_count
    evidence.append(f"slide_count:{slide_count}")
    expected_slides = constraints.get("required_slide_count", constraints.get("required_slides"))
    if isinstance(expected_slides, int) and slide_count != expected_slides:
        failures.append(f"slide count expected {expected_slides}, got {slide_count}")
    marker = str(constraints.get("required_text", ""))
    texts = [shape.text for slide in presentation.slides for shape in slide.shapes if hasattr(shape, "text")]
    marker_ok = not marker or any(marker in text for text in texts)
    dimensions["marker_correctness"] = 1.0 if marker_ok else 0.0
    if not marker_ok:
        failures.append(f"required marker missing: {marker}")
    expected_texts = constraints.get("required_shape_text", [])
    text_checks = len(expected_texts) if isinstance(expected_texts, list) else 0
    text_passes = sum(any(str(expected) in text for text in texts) for expected in expected_texts) if isinstance(expected_texts, list) else 0
    if text_checks and text_passes != text_checks:
        failures.append("one or more required PowerPoint shape texts are missing")
    dimensions["text_structure_correctness"] = _ratio(text_checks, text_passes)
    structure_checks = 1 + (1 if isinstance(expected_slides, int) else 0) + text_checks
    structure_passes = 1 + (1 if isinstance(expected_slides, int) and slide_count == expected_slides else 0) + text_passes
    dimensions["structure_correctness"] = _ratio(structure_checks, structure_passes)
    channels["structure"] = "available"
    geometry = check_powerpoint_geometry(path)
    metadata["geometry"] = {
        "slide_count": geometry.slide_count,
        "overlap_count": geometry.overlap_count,
        "overflow_count": geometry.overflow_count,
        "empty_slide_count": geometry.empty_slide_count,
    }
    evidence.extend(geometry.evidence)
    warnings.extend(geometry.warnings)
    failures.extend(geometry.failures)
    channels.update(geometry.channel_status)
    dimensions["geometry_correctness"] = 1.0 if geometry.passed else 0.0
    dimensions["rendering_correctness"] = 1.0 if geometry.channel_status.get("rendering") == "available" and geometry.passed else 0.0
    # Rendering is unavailable in this environment, so do not treat its zero
    # placeholder as a failure or include it in the aggregate score.
    if geometry.channel_status.get("rendering") != "available":
        dimensions.pop("rendering_correctness", None)


def inspect_office_file(path: str | Path, task: TaskSpec) -> OfficeCheckReport:
    """Inspect one Office package against task constraints.

    Any unreadable package or unmet hard constraint is a failure.  Optional
    visual rendering is represented by ``channel_status`` and warnings.
    """

    source = Path(path)
    domain = task.domain.lower()
    metadata, failures, warnings, evidence, dimensions, channels = _base_report(source, domain)
    if domain not in MEDIA_TYPES:
        failures.append(f"unsupported Office domain: {task.domain}")
        return OfficeCheckReport(path=str(source), domain=domain, status="failed", passed=False, dimensions=dimensions, failures=failures, warnings=warnings, evidence=evidence, channel_status=channels, metadata=metadata, artifact_sha256=evidence[0].split(":", 1)[1] if evidence and evidence[0].startswith("artifact_sha256:") else None, size_bytes=source.stat().st_size if source.exists() else 0)

    if not source.exists() or failures:
        dimensions["format_validity"] = 0.0
        dimensions["marker_correctness"] = 0.0
        return OfficeCheckReport(path=str(source), domain=domain, status="failed", passed=False, dimensions=dimensions, failures=failures, warnings=warnings, evidence=evidence, channel_status=channels, metadata=metadata, artifact_sha256=evidence[0].split(":", 1)[1] if evidence and evidence[0].startswith("artifact_sha256:") else None, size_bytes=source.stat().st_size if source.exists() else 0)

    try:
        constraints = dict(task.expected_constraints)
        if domain == "excel":
            _excel_checks(source, constraints, failures, evidence, dimensions, channels, metadata)
        elif domain == "word":
            _word_checks(source, constraints, failures, evidence, dimensions, channels, metadata)
        else:
            _powerpoint_checks(source, constraints, failures, warnings, evidence, dimensions, channels, metadata)
        dimensions["format_validity"] = 0.0 if failures and any("OOXML" in item or "format" in item.lower() or "suffix" in item.lower() for item in failures) else 1.0
    except Exception as exc:
        failures.append(f"{domain} structure inspection failed: {exc}")
        dimensions["format_validity"] = 0.0
        channels["structure"] = "failed"

    passed = not failures
    return OfficeCheckReport(
        path=str(source),
        domain=domain,
        status="available" if passed else "failed",
        passed=passed,
        artifact_sha256=evidence[0].split(":", 1)[1] if evidence and evidence[0].startswith("artifact_sha256:") else None,
        size_bytes=source.stat().st_size,
        dimensions=dimensions,
        failures=failures,
        warnings=warnings,
        evidence=evidence,
        channel_status=channels,
        metadata=metadata,
    )


__all__ = ["OfficeCheckReport", "inspect_office_file"]
