"""Read-only shared observations and standalone JSON entry point for both skills."""

from __future__ import annotations

import argparse
from datetime import date, datetime, time as datetime_time
import json
import math
from pathlib import Path
from typing import Any
import zipfile

from pydantic import TypeAdapter

from .assessment_contracts import AcceptanceSpec, Assessment, CheckRecord, Evidence, Location, Requirement
from .hashing import canonical_json_hash, sha256_file
from .office_checks import EXPECTED_SUFFIXES, OOXML_MEMBERS


KNOWN = {"PASS", "PARTIAL", "FAIL"}
JSON_VALUE = TypeAdapter(Any)


def assessment_identity(config: dict | None = None) -> str:
    root = Path(__file__).resolve().parents[2]
    names = ("assessment_contracts.py", "artifact_assessment.py", "artifact_evaluator.py", "artifact_verifier.py", "sales_assessment.py", "office_checks.py", "artifact_renderer.py", "judgement_provider.py", "semantic_assessment.py", "model_judgement.py")
    files = {name: sha256_file(Path(__file__).with_name(name)) for name in names if Path(__file__).with_name(name).exists()}
    for skill in ("office-artifact-evaluator", "office-artifact-verifier"):
        for path in sorted((root / "skills" / skill).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                files[path.relative_to(root).as_posix()] = sha256_file(path)
    return canonical_json_hash({"files": files, "configuration": config or {}, "mode": "artifact-assessment-v1"})


def _equal(actual: Any, expected: Any, tolerance: float) -> bool:
    if isinstance(actual, (date, datetime, datetime_time)) and isinstance(expected, str):
        return actual.isoformat() == expected
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(actual) and abs(actual - expected) <= tolerance
    return actual == expected


class SharedAssessment:
    def __init__(self, *, visual=None, semantic=None):
        self.visual, self.semantic = visual, semantic

    def identity(self) -> str:
        return assessment_identity({"visual": self.visual.identity_config() if self.visual else "disabled",
                                    "semantic": self.semantic.identity_config() if self.semantic else "disabled"})

    def inspect(self, spec: AcceptanceSpec, artifacts: dict[str, str | Path]) -> Assessment:
        spec = AcceptanceSpec.model_validate(spec.model_dump(mode="json"))
        paths = {key: Path(value) for key, value in artifacts.items() if key in spec.artifacts}
        hashes = {key: sha256_file(paths[key]) if key in paths and paths[key].is_file() else None for key in spec.artifacts}
        for raw_path, digest in spec.input_hashes.items():
            if not Path(raw_path).is_file() or sha256_file(raw_path) != digest:
                raise ValueError("frozen assessment input changed: " + raw_path)
        parsed = {}
        parse_errors = {}
        for key, domain in spec.artifacts.items():
            path = paths.get(key)
            if path is None or not path.is_file():
                parse_errors[key] = "artifact missing"
                continue
            try:
                if path.suffix.lower() != EXPECTED_SUFFIXES[domain]:
                    raise ValueError("unexpected artifact extension")
                with zipfile.ZipFile(path) as package:
                    if not set(OOXML_MEMBERS[domain]).issubset(package.namelist()):
                        raise ValueError("required OOXML members missing")
                if domain == "excel":
                    from openpyxl import load_workbook
                    parsed[key] = load_workbook(path, data_only=False)
                elif domain == "word":
                    from docx import Document
                    parsed[key] = Document(path)
                else:
                    from pptx import Presentation
                    parsed[key] = Presentation(path)
            except Exception as exc:
                parse_errors[key] = f"artifact cannot be parsed: {type(exc).__name__}: {exc}"
        checks, evidence, telemetry = [], [], {"visual": [], "semantic": []}
        try:
            for r in spec.requirements:
                location = r.location
                message = ""
                if not r.applicable:
                    status, completion, observed = "NOT_APPLICABLE", None, r.applicability_reason
                elif r.location.artifact in parse_errors:
                    status, completion, observed = "FAIL", 0, parse_errors[r.location.artifact]
                else:
                    try:
                        if r.check in {"visual", "semantic"}:
                            channel = self.visual if r.check == "visual" else self.semantic
                            if channel is None:
                                status, completion, observed = "UNAVAILABLE", None, r.check + " channel disabled"
                            else:
                                source = paths[r.location.artifact] if r.check == "visual" else parsed[r.location.artifact]
                                result = channel.check(r, source, hashes[r.location.artifact])
                                status, completion, observed = result["status"], result.get("completion"), result.get("observed")
                                if result.get("location"):
                                    location = Location.model_validate(result["location"])
                                telemetry[r.check].append(result.get("telemetry", {}))
                        else:
                            status, completion, observed, location = self._check(r, parsed, paths)
                    except ImportError as exc:
                        status, completion, observed = "UNAVAILABLE", None, str(exc)
                    except Exception as exc:
                        status, completion, observed = "ERROR", None, f"{type(exc).__name__}: {exc}"
                if status not in KNOWN:
                    message = str(observed)
                json_observed = JSON_VALUE.dump_python(observed, mode="json")
                item = Evidence(evidence_id=canonical_json_hash({"spec": spec.fingerprint(), "requirement": r.requirement_id, "hashes": hashes, "status": status, "observed": json_observed}),
                                requirement_id=r.requirement_id, location=location, source=r.evidence_source,
                                observed=observed, artifact_sha256=hashes[r.location.artifact], artifact_hashes=hashes)
                evidence.append(item)
                checks.append(CheckRecord(requirement_id=r.requirement_id, status=status, completion=completion,
                                          location=location, observed=observed, expected=r.expected,
                                          evidence_refs=[item.evidence_id], message=message))
        finally:
            for obj in parsed.values():
                if hasattr(obj, "close"):
                    obj.close()
        # A concurrently changed file invalidates the snapshot, not the artifact's score.
        if any(sha256_file(paths[k]) != h for k, h in hashes.items() if h is not None):
            raise ValueError("artifact changed during inspection")
        return Assessment(spec=spec, spec_hash=spec.fingerprint(), evaluator_identity=self.identity(),
                          artifact_hashes=hashes, checks=checks, evidence=evidence, telemetry=telemetry)

    def _check(self, r, parsed, paths):
        obj, loc = parsed[r.location.artifact], r.location
        if r.check == "file.readable":
            actual = True
        elif r.check == "file.format":
            reverse_suffixes = {suffix: domain for domain, suffix in EXPECTED_SUFFIXES.items()}
            actual = reverse_suffixes.get(paths[loc.artifact].suffix.lower(), "unknown")
        elif r.check == "excel.sheets":
            actual = list(obj.sheetnames)
            return self._fraction(r, [name in actual for name in r.expected], actual, loc)
        elif r.check.startswith("excel."):
            if loc.sheet not in obj.sheetnames:
                return "FAIL", 0, "worksheet missing", loc
            sheet = obj[loc.sheet]
            if r.check in {"excel.cell", "excel.formula", "excel.number_format"}:
                cell = sheet[loc.cell]
                actual = cell.number_format if r.check == "excel.number_format" else cell.value
            elif r.check == "excel.range":
                actual = [[cell.value for cell in row] for row in sheet[loc.cell]]
                flags = [i < len(actual) and j < len(actual[i]) and _equal(actual[i][j], value, r.tolerance) for i, row in enumerate(r.expected) for j, value in enumerate(row)]
                return self._fraction(r, flags, actual, loc)
            elif r.check == "excel.cached_value":
                from openpyxl import load_workbook
                cached = load_workbook(paths[loc.artifact], data_only=True)
                try:
                    actual = cached[loc.sheet][loc.cell].value
                finally:
                    cached.close()
                if actual is None:
                    return "UNAVAILABLE", None, "no cached value; openpyxl does not recalculate formulas", loc
            elif r.check == "excel.recalculated_value":
                return "UNAVAILABLE", None, "no recalculation engine configured", loc
            elif r.check == "excel.chart":
                actual = []
                for chart in sheet._charts:
                    for series in chart.series:
                        values = getattr(getattr(series, "val", None), "numRef", None)
                        categories = getattr(series, "cat", None)
                        categories = getattr(categories, "numRef", None) or getattr(categories, "strRef", None)
                        actual.append({"values": getattr(values, "f", None), "categories": getattr(categories, "f", None)})
                return self._fraction(r, [item in actual for item in r.expected], actual, loc)
            else:
                return "UNAVAILABLE", None, "unsupported check: " + r.check, loc
        elif r.check == "text.contains":
            texts = self._texts(obj)
            matched = [(text, position) for text, position in texts if str(r.expected) in text]
            actual = matched[0][0] if matched else "required content not found"
            if matched:
                loc = loc.model_copy(update=matched[0][1])
            return ("PASS", 1, actual, loc) if matched else ("FAIL", 0, actual, loc)
        elif r.check == "word.headings":
            actual = [p.text for p in obj.paragraphs if p.style and p.style.name.startswith("Heading")]
            return self._fraction(r, [item in actual for item in r.expected], actual, loc)
        elif r.check == "word.heading_style":
            matches = [(i, p) for i, p in enumerate(obj.paragraphs, 1) if p.text == loc.heading]
            actual = matches[0][1].style.name if matches else None
            if matches:
                loc = loc.model_copy(update={"paragraph": matches[0][0]})
        elif r.check == "word.references":
            actual = [rel.target_ref for rel in obj.part.rels.values() if rel.reltype.endswith("/hyperlink") and rel.is_external]
            return self._fraction(r, [ref in actual for ref in r.expected], actual, loc)
        elif r.check in {"word.paragraph", "word.table_cell", "powerpoint.object_text"}:
            actual = self._fact(obj, loc)
        elif r.check == "powerpoint.slide_count":
            actual = len(obj.slides)
        elif r.check == "powerpoint.texts":
            texts = [text for text, _ in self._texts(obj)]
            return self._fraction(r, [any(str(wanted) in text for text in texts) for wanted in r.expected], texts, loc)
        elif r.check == "powerpoint.chart_values":
            shape = next((s for s in obj.slides[loc.slide - 1].shapes if s.shape_id == loc.object_id), None)
            actual = [list(series.values) for series in shape.chart.series] if shape is not None and shape.has_chart else None
        elif r.check in {"powerpoint.bounds", "powerpoint.overlap"}:
            shapes = list(obj.slides[loc.slide - 1].shapes)
            if r.check == "powerpoint.bounds":
                actual = [s.shape_id for s in shapes if s.left < 0 or s.top < 0 or s.left + s.width > obj.slide_width or s.top + s.height > obj.slide_height]
            else:
                actual = []
                for i, a in enumerate(shapes):
                    for b in shapes[i + 1:]:
                        ax, ay, bx, by = a.left + a.width, a.top + a.height, b.left + b.width, b.top + b.height
                        intersects = max(a.left, b.left) < min(ax, bx) and max(a.top, b.top) < min(ay, by)
                        contained = (a.left <= b.left and a.top <= b.top and ax >= bx and ay >= by) or (b.left <= a.left and b.top <= a.top and bx >= ax and by >= ay)
                        # Containment and backgrounds are legal geometric arrangements.
                        if intersects and not contained:
                            actual.append([a.shape_id, b.shape_id])
                if actual:
                    return "NEEDS_REVIEW", None, {"intersections": actual, "note": "geometry alone cannot establish visual occlusion"}, loc
        elif r.check == "facts.consistent":
            actual, flags = [], []
            for payload in r.options["locations"]:
                position = Location.model_validate(payload)
                value = self._fact(parsed[position.artifact], position) if position.artifact in parsed else "artifact missing or unreadable"
                actual.append({"location": position.model_dump(exclude_none=True), "value": value})
                equal = _equal(value, r.expected, r.tolerance)
                if not equal:
                    loc = position
                flags.append(equal)
            return self._fraction(r, flags, actual, loc)
        else:
            return "UNAVAILABLE", None, "unsupported check: " + r.check, loc
        passed = _equal(actual, r.expected, r.tolerance)
        return ("PASS" if passed else "FAIL"), (1 if passed else 0), actual, loc

    @staticmethod
    def _fact(obj, loc):
        if loc.sheet:
            return obj[loc.sheet][loc.cell].value if loc.sheet in obj.sheetnames else None
        if loc.paragraph:
            return obj.paragraphs[loc.paragraph - 1].text if loc.paragraph <= len(obj.paragraphs) else None
        if loc.table:
            if loc.table > len(obj.tables):
                return None
            table = obj.tables[loc.table - 1]
            return table.cell(loc.row - 1, loc.column - 1).text if loc.row <= len(table.rows) and loc.column <= len(table.columns) else None
        if loc.slide:
            if loc.slide > len(obj.slides):
                return None
            shape = next((s for s in obj.slides[loc.slide - 1].shapes if s.shape_id == loc.object_id), None)
            return shape.text if shape is not None and hasattr(shape, "text") else None
        raise ValueError("fact location needs sheet/cell, paragraph, table coordinates, or slide/object")

    @staticmethod
    def _fraction(r, flags, actual, loc):
        if not flags:
            raise ValueError("empty expected collection; mark the requirement not applicable instead")
        fraction = sum(flags) / len(flags)
        return ("PASS" if fraction == 1 else "FAIL" if fraction == 0 else "PARTIAL"), fraction, actual, loc

    @staticmethod
    def _texts(obj):
        if hasattr(obj, "worksheets"):
            return [(str(c.value), {"sheet": sheet.title, "cell": c.coordinate}) for sheet in obj.worksheets for row in sheet for c in row if c.value is not None]
        if hasattr(obj, "paragraphs"):
            items, heading = [], None
            for i, p in enumerate(obj.paragraphs, 1):
                if p.style and p.style.name.startswith("Heading"):
                    heading = p.text
                items.append((p.text, {"paragraph": i, "heading": heading}))
            items.extend((c.text, {"table": t, "row": i, "column": j}) for t, table in enumerate(obj.tables, 1) for i, row in enumerate(table.rows, 1) for j, c in enumerate(row.cells, 1))
            return items
        return [(shape.text, {"slide": i, "object_id": shape.shape_id}) for i, slide in enumerate(obj.slides, 1) for shape in slide.shapes if hasattr(shape, "text")]


def spec_from_task(task) -> AcceptanceSpec:
    """Adapt existing constraints explicitly; unsupported constraints stay visible."""
    constraints = task.expected_constraints
    if constraints.get("sales_summary"):
        from .sales_assessment import sales_spec
        return sales_spec(task)
    if "acceptance_spec" in constraints:
        spec = AcceptanceSpec.model_validate(constraints["acceptance_spec"])
        if spec.task_id != task.task_id:
            raise ValueError("acceptance specification task identity mismatch")
        return spec
    requirements = [Requirement(requirement_id="file", description="Readable required artifact", check="file.readable", location=Location(artifact="output"), expected=True, critical=True, dimension="correctness", evidence_source="OOXML package and library parser")]
    adapters = {"required_text": "text.contains", "marker": "text.contains", "output_format": "file.format", "required_sheets": "excel.sheets", "required_cells": "excel.cell", "required_formulas": "excel.formula", "required_formula_values": "excel.cached_value", "required_headings": "word.headings", "required_heading_styles": "word.heading_style", "required_slide_count": "powerpoint.slide_count", "required_slides": "powerpoint.slide_count", "required_shape_text": "powerpoint.texts"}
    for key, expected in constraints.items():
        if key == "marker" and constraints.get("required_text") == expected:
            continue
        check = adapters.get(key, "unsupported." + key)
        entries = expected.items() if key in {"required_cells", "required_formulas", "required_formula_values", "required_heading_styles"} else [("", expected)]
        for target, value in entries:
            position = {"artifact": "output"}
            if "!" in target:
                position["sheet"], position["cell"] = target.rsplit("!", 1)
                position["sheet"] = position["sheet"].strip("'")
            elif key == "required_heading_styles":
                position["heading"] = target
            elif target:
                position["cell"] = target
            if key == "output_format":
                value = str(value).lower()
            requirements.append(Requirement(requirement_id=f"{key}:{target}", description=key, check=check, location=Location(**position), expected=value, critical=True, dimension="correctness", evidence_source="TaskSpec.expected_constraints"))
    domain = task.domain.lower()
    return AcceptanceSpec(task_id=task.task_id, version="legacy-constraints-v1", artifacts={"output": domain}, requirements=requirements, dimension_weights={"correctness": 1})


def assess(spec, artifacts, *, visual=None, semantic=None):
    from .artifact_evaluator import ArtifactEvaluator
    from .artifact_verifier import ArtifactVerifier
    shared = SharedAssessment(visual=visual, semantic=semantic).inspect(spec, artifacts)
    return shared, ArtifactEvaluator().evaluate(shared), ArtifactVerifier().verify(shared)


def save_reports(output, shared, score, issues):
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    for name, report in (("assessment", shared), ("score", score), ("issues", issues)):
        target = root / f"{name}.json"
        with target.open("x", encoding="utf-8") as stream:
            stream.write(report.model_dump_json(indent=2))
    text = f"# Artifact assessment: {score.task_id}\n\nAcceptance: {score.acceptance_status}\n\nQuality: {score.total_score} / 100\n\nCoverage: {score.coverage.completed}/{score.coverage.applicable}\n\n{score.scope_note}\n\n"
    for issue in issues.issues:
        text += f"- {issue.requirement_id}: {issue.kind}; {issue.location.model_dump(exclude_none=True)}; observed={issue.observed!r}; expected={issue.expected!r}. {issue.repair_hint}\n"
    (root / "report.md").write_text(text, encoding="utf-8")


def main(argv=None, *, entry="both"):
    parser = argparse.ArgumentParser(description="Assess real Office artifacts with a frozen specification")
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, help="Trusted JSON model configuration (codex-cli, api or disabled)")
    args = parser.parse_args(argv)
    request = json.loads(args.request.read_text(encoding="utf-8-sig"))
    spec = AcceptanceSpec.model_validate(request["spec"])
    artifacts = {key: str((args.request.resolve().parent / value).resolve()) for key, value in request["artifacts"].items()}
    if args.model_config:
        from .model_judgement import configured_assessment
        from .artifact_evaluator import ArtifactEvaluator
        from .artifact_verifier import ArtifactVerifier
        config = json.loads(args.model_config.read_text(encoding="utf-8-sig"))
        engine = configured_assessment(config, args.output / "model-evidence")
        shared = engine.inspect(spec, artifacts)
        score, issues = ArtifactEvaluator().evaluate(shared), ArtifactVerifier().verify(shared)
    else:
        shared, score, issues = assess(spec, artifacts)
    save_reports(args.output, shared, score, issues)
    print((issues if entry == "verifier" else score).model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
