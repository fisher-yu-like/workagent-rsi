"""Run real non-Ollama API Office tasks through the current Harness."""

from __future__ import annotations

import json
import os
from pathlib import Path

from workagent_rsi.harness import Harness
from workagent_rsi.workagent_provider import WorkAgentConfig


ROOT = Path(__file__).resolve().parents[2]
RESULT_ROOT = ROOT / "results" / "rsi-live-api-20261011"
MODEL = "claude-haiku-4-5-20251001"


def task(domain: str) -> dict:
    prompts = {
        "excel": "Create outputs/live_sales.xlsx with worksheet Summary. Put header Region in A1 and Sales in B1. Put East in A2 and 15 in B2. Put West in A3 and 10 in B3. Add formula =SUM(B2:B3) in B4. Use a two-decimal number format for B2:B4. Reopen the workbook and verify every requested value and formula.",
        "word": "Create outputs/live_memo.docx. Add Heading 1 exactly 'Live API Leadership Memo'. Add a paragraph containing exactly 'LIVE-API-WORD-20261011'. Reopen the document and verify the heading style and marker.",
        "powerpoint": "Create outputs/live_review.pptx with exactly one slide. The slide title must be exactly 'Live API Executive Review'. Its body must contain exactly 'LIVE-API-PPT-20261011'. Reopen the presentation and verify the slide count and both text strings.",
    }
    constraints = {
        "excel": {"required_sheets": ["Summary"], "required_cells": {"Summary!A1": "Region", "Summary!B2": 15, "Summary!B3": 10}, "required_formulas": {"Summary!B4": "=SUM(B2:B3)"}, "required_text": "Region"},
        "word": {"required_text": "LIVE-API-WORD-20261011", "required_headings": ["Live API Leadership Memo"], "required_heading_styles": {"Live API Leadership Memo": "Heading 1"}},
        "powerpoint": {"required_slide_count": 1, "required_shape_text": ["Live API Executive Review", "LIVE-API-PPT-20261011"]},
    }
    return {"task_id": f"live-api-{domain}", "domain": domain, "instruction": prompts[domain], "expected_constraints": constraints[domain], "risk_level": "low"}


def main() -> None:
    RESULT_ROOT.mkdir(parents=True, exist_ok=False)
    config = WorkAgentConfig(backend="openai-chat", model=MODEL, api_base_url=os.environ["OPENAI_BASE_URL"], timeout_seconds=180, max_tool_turns=12, verify_com=False)
    rows = []
    for domain in ("excel", "word", "powerpoint"):
        result = Harness(RESULT_ROOT, execution_provider="workagent", workagent_config=config).run(task(domain))
        row = {"domain": domain, "state": result["state"], "result_dir": result["result_dir"], "failure": result.get("failure"), "evaluation": result.get("evaluation")}
        assessment_dir = Path(result["result_dir"]) / "assessment"
        if (assessment_dir / "score.json").exists():
            row["score"] = json.loads((assessment_dir / "score.json").read_text(encoding="utf-8"))
            row["issues"] = json.loads((assessment_dir / "issues.json").read_text(encoding="utf-8"))
        rows.append(row)
    (RESULT_ROOT / "summary.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
