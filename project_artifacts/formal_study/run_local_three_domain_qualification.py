"""Serial local Office qualification across Excel, Word, and PowerPoint."""

from __future__ import annotations

import json
from pathlib import Path

from workagent_rsi.harness import Harness


ROOT = Path(__file__).resolve().parents[2]
RESULT_ROOT = ROOT / "results" / "qualification" / "three-domain-local-current-src-20261011"

ROUNDS = (
    ("regional-summary", "ROUND-01-VERIFIED", [{"region": "East", "amount": 15}, {"region": "West", "amount": 10}, {"region": "East", "amount": 5}]),
    ("productivity-review", "ROUND-02-VERIFIED", [{"region": "North", "amount": 8.5}, {"region": "South", "amount": 11.25}, {"region": "North", "amount": 1.5}]),
    ("board-pack", "ROUND-03-VERIFIED", [{"region": "Central", "amount": 12}, {"region": "Coastal", "amount": 20}, {"region": "Central", "amount": 3}]),
)


def build_task(round_name: str, marker: str, domain: str, source: Path) -> dict:
    prompts = {
        "excel": f"Create a complete regional sales workbook for {round_name}, with all transactions, totals, formulas, number formats and a chart.",
        "word": f"Write the leadership memo for {round_name}.",
        "powerpoint": f"Create the executive slide for {round_name}.",
    }
    task = {
        "task_id": f"{round_name}-{domain}",
        "domain": domain,
        "instruction": prompts[domain],
        "risk_level": "low",
        "expected_constraints": {"required_text": marker},
    }
    if domain == "excel":
        task["input_files"] = [str(source)]
        task["expected_constraints"] = {"sales_summary": True}
    elif domain == "word":
        task["expected_constraints"].update({"required_headings": [prompts[domain]], "required_heading_styles": {prompts[domain]: "Heading 1"}})
    else:
        task["expected_constraints"].update({"required_slide_count": 1, "required_shape_text": [prompts[domain], marker]})
    return task


def main() -> None:
    RESULT_ROOT.mkdir(parents=True, exist_ok=False)
    inputs = RESULT_ROOT / "inputs"
    inputs.mkdir()
    rows = []
    for round_name, marker, records in ROUNDS:
        source = inputs / f"{round_name}.json"
        source.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        for domain in ("excel", "word", "powerpoint"):
            task = build_task(round_name, marker, domain, source)
            result = Harness(RESULT_ROOT, execution_provider="local_office").run(task)
            assessment_root = Path(result["result_dir"]) / "assessment"
            score = json.loads((assessment_root / "score.json").read_text(encoding="utf-8"))
            issues = json.loads((assessment_root / "issues.json").read_text(encoding="utf-8"))
            rows.append({
                "round": round_name,
                "domain": domain,
                "prompt": task["instruction"],
                "state": result["state"],
                "acceptance": score["acceptance_status"],
                "score": score["total_score"],
                "issues": len(issues["issues"]),
                "result_dir": result["result_dir"],
                "artifact": result["artifacts"][0]["path"] if result.get("artifacts") else None,
            })
    (RESULT_ROOT / "summary.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result_root": str(RESULT_ROOT), "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
