"""Bounded, location-aware text evidence and semantic assessment without rendering."""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree.ElementTree import tostring

from pydantic import Field

from .assessment_contracts import AssessmentModel
from .hashing import canonical_json_hash
from .judgement_provider import VisualJudgement


class SemanticObservation(AssessmentModel):
    evidence_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    observation: str = Field(min_length=1)


class SemanticJudgement(VisualJudgement):
    observations: list[SemanticObservation] = Field(min_length=1)


class EvidenceBudgetExceeded(ValueError):
    pass


def extract_evidence(obj, artifact, *, max_chars=60000, max_items=2000):
    """Never silently truncate. Unsupported embedded content is declared explicitly."""
    items, used = [], 0

    def add(text, **location):
        nonlocal used
        text = str(text)
        if not text.strip():
            return
        entry = {"evidence_id": f"e{len(items) + 1}", "location": {"artifact": artifact, **location}, "text": text}
        used += len(json.dumps(entry, ensure_ascii=False))
        if used > max_chars or len(items) >= max_items:
            raise EvidenceBudgetExceeded("semantic evidence exceeds configured character/item budget; split the requirement or increase the fixed budget")
        items.append(entry)

    limitations = ["Embedded images, drawings and page appearance require a visual check."]
    if hasattr(obj, "worksheets"):
        limitations.append("Formula strings are not recalculated values; numerical correctness belongs to deterministic checks.")
        for sheet in obj.worksheets:
            # Avoid iterating billions of empty cells in a formatting-expanded sheet.
            if sheet.max_row * sheet.max_column > max_items * 100:
                raise EvidenceBudgetExceeded("worksheet used range exceeds semantic extraction budget")
            add(f"Worksheet: {sheet.title}", sheet=sheet.title)
            for row in sheet:
                for cell in row:
                    if cell.value is not None:
                        add(cell.value, sheet=sheet.title, cell=cell.coordinate)
            for i, chart in enumerate(sheet._charts, 1):
                add(tostring(chart.to_tree(), encoding="unicode"), sheet=sheet.title, region=f"chart {i}")
    elif hasattr(obj, "paragraphs"):
        # Preserve body paragraph/table order rather than appending all tables at the end.
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        p_index = t_index = 0
        heading = None
        for child in obj.element.body:
            if child.tag.endswith("}p"):
                p_index += 1
                p = Paragraph(child, obj)
                style = p.style.name if p.style else ""
                if style.startswith("Heading"):
                    heading = p.text
                add(p.text, paragraph=p_index, heading=heading, region=f"style: {style}")
            elif child.tag.endswith("}tbl"):
                t_index += 1
                table = Table(child, obj)
                for r, row in enumerate(table.rows, 1):
                    for c, cell in enumerate(row.cells, 1):
                        add(cell.text, table=t_index, row=r, column=c)
        limitations.append("Headers, footers, comments and embedded objects are outside this body-text extraction.")
    else:
        def shapes(items):
            for shape in items:
                yield shape
                if hasattr(shape, "shapes"):
                    yield from shapes(shape.shapes)
        for i, slide in enumerate(obj.slides, 1):
            add(f"Slide {i}", slide=i)
            for shape in shapes(slide.shapes):
                loc = {"slide": i, "object_id": shape.shape_id}
                if getattr(shape, "has_text_frame", False):
                    add(shape.text, **loc)
                if getattr(shape, "has_table", False):
                    for r, row in enumerate(shape.table.rows, 1):
                        for c, cell in enumerate(row.cells, 1):
                            add(cell.text, row=r, column=c, **loc)
                if getattr(shape, "has_chart", False):
                    chart = shape.chart
                    categories = [str(c.label) for c in chart.plots[0].categories]
                    for series in chart.series:
                        add(json.dumps({"series": series.name, "categories": categories, "values": list(series.values)}, ensure_ascii=False), **loc)
        limitations.append("Speaker notes are outside this slide-content extraction.")
    return {"items": items, "limitations": limitations, "complete_within_declared_scope": True}


def validate_semantic_evidence(decision, request):
    valid = {item["evidence_id"]: item for item in request["evidence"]["items"]}
    for observation in decision.observations:
        if observation.evidence_id not in valid or observation.quote not in valid[observation.evidence_id]["text"]:
            raise ValueError("semantic evidence ID or exact quote does not map to supplied content")


class SemanticAssessmentChannel:
    def __init__(self, provider, cache_root, *, max_chars=60000, max_items=2000, cache_enabled=True):
        self.provider, self.cache_root = provider, Path(cache_root)
        self.max_chars, self.max_items, self.cache_enabled = max_chars, max_items, cache_enabled

    def identity_config(self):
        return {"semantic": "text-evidence-v1", "provider": self.provider.identity_config(),
                "max_chars": self.max_chars, "max_items": self.max_items, "cache_enabled": self.cache_enabled}

    def check(self, requirement, obj, artifact_sha256):
        def gap(status, message, telemetry=None):
            return {"status": status, "completion": None, "observed": message, "telemetry": telemetry or {"model_calls": 0}}
        try:
            evidence = extract_evidence(obj, requirement.location.artifact, max_chars=self.max_chars, max_items=self.max_items)
        except EvidenceBudgetExceeded as exc:
            return gap("UNAVAILABLE", str(exc))
        if not evidence["items"]:
            return gap("NEEDS_REVIEW", "no text evidence; use a visual check for scanned or image-only content")
        request = {"modality": "semantic", "requirement": requirement.model_dump(mode="json"),
                   "artifact_sha256": artifact_sha256, "evidence": evidence, "images": []}
        key = canonical_json_hash({"request": request, "identity": self.identity_config()})
        work = self.cache_root / key
        cached = work / "cache.json"
        hit = self.cache_enabled and cached.is_file()
        try:
            if hit:
                payload = json.loads(cached.read_text(encoding="utf-8"))
                decision = SemanticJudgement.model_validate(payload["decision"])
                telemetry = {**payload["telemetry"], "model_calls": 0, "cache_hit": True}
            else:
                decision, telemetry = self.provider.judge(request, work)
                telemetry = {**telemetry, "cache_hit": False}
                if decision is None:
                    return gap("UNAVAILABLE" if telemetry.get("status") in {"unavailable", "timeout"} else "ERROR", telemetry.get("error"), telemetry)
            validate_semantic_evidence(decision, request)
        except (ValueError, OSError) as exc:
            return gap("ERROR", str(exc))
        if not hit and self.cache_enabled:
            work.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps({"decision": decision.model_dump(mode="json"), "telemetry": telemetry}, ensure_ascii=False, indent=2), encoding="utf-8")
        mapped = {i["evidence_id"]: i["location"] for i in evidence["items"]}
        observations = [{**o.model_dump(mode="json"), "location": mapped[o.evidence_id]} for o in decision.observations]
        return {"status": decision.status, "completion": decision.completion,
                "location": mapped[decision.observations[0].evidence_id],
                "observed": {"summary": decision.observed, "confidence": decision.confidence, "observations": observations, "scope": evidence["limitations"]}, "telemetry": telemetry}
