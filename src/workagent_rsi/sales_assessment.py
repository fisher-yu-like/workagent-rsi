"""Independent input-derived acceptance for the first, bounded spreadsheet family."""

import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from .assessment_contracts import AcceptanceSpec, Location, Requirement
from .hashing import sha256_file


def sales_spec(task) -> AcceptanceSpec:
    if len(task.input_files) != 1:
        raise ValueError("sales_summary requires one frozen JSON input file")
    source = Path(task.input_files[0]).resolve()
    records = json.loads(source.read_text(encoding="utf-8"))
    totals = defaultdict(Decimal)
    for record in records:
        amount = Decimal(str(record["amount"]))
        if not amount.is_finite() or not isinstance(record["region"], str) or not record["region"]:
            raise ValueError("invalid sales input")
        totals[record["region"]] += amount
    if not totals:
        raise ValueError("sales input cannot be empty")
    regions = sorted(totals)
    requirements = []

    def add(rid, check, expected, dim, *, cell=None, sheet="Summary", critical=False, hint=None, weight=1):
        requirements.append(Requirement(requirement_id=rid, description=rid, check=check,
            location=Location(artifact="output", sheet=sheet, cell=cell), expected=expected,
            critical=critical, dimension=dim, weight=weight, tolerance=0.005,
            evidence_source=f"independent Decimal aggregation of input sha256:{sha256_file(source)}",
            repair_hint=f"Regenerate {sheet}!{cell or ''} using every original sales record and the frozen requirement.",
            skill_improvement_hint=hint))

    add("readable", "file.readable", True, "structure", critical=True)
    add("sheets", "excel.sheets", ["Summary", "Data"], "structure", critical=True)
    add("source_records", "excel.range", [[r["region"], r["amount"]] for r in records], "completeness", sheet="Data", cell=f"A2:B{len(records)+1}", critical=True)
    add("headers", "excel.range", [["Region", "Sales", "Formula (recalculate in Office)"]], "structure", cell="A1:C1")
    for row, region in enumerate(regions, 2):
        add(f"total.{region}", "excel.cell", float(totals[region]), "correctness", cell=f"B{row}", critical=True, hint="sales_rows=all: derive the aggregation boundary from the complete input length")
        add(f"formula.{region}", "excel.formula", f'=SUMIF(Data!A2:A{len(records)+1},A{row},Data!B2:B{len(records)+1})', "correctness", cell=f"C{row}", critical=True, weight=0, hint="sales_rows=all: derive the aggregation boundary from the complete input length")
        add(f"format.{region}", "excel.number_format", '#,##0.00', "presentation", cell=f"B{row}", hint="sales_number_format=true: format sales totals to two decimal places")
    add("chart", "excel.chart", [{"values": f"'Summary'!$B$2:$B${len(regions)+1}", "categories": f"'Summary'!$A$2:$A${len(regions)+1}"}], "completeness", hint="sales_chart=true: chart the entire region summary")
    return AcceptanceSpec(task_id=task.task_id, version="sales-summary-v1", artifacts={"output": "excel"}, requirements=requirements,
        dimension_weights={"correctness": .5, "completeness": .25, "structure": .15, "presentation": .1},
        quality_threshold=80, input_hashes={str(source): sha256_file(source)},
        scope_note="Project-generated sales task: typed totals, exact formula coverage, source rows, chart references and number format. Formula caches/recalculation and visual appearance are not claimed.")
