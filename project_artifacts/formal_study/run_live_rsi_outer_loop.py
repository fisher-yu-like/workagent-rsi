"""Run one real non-Ollama WorkAgent RSI outer-loop round."""

from __future__ import annotations

import json
import os
from pathlib import Path

from workagent_rsi.contracts import TaskSpec
from workagent_rsi.candidate_provider import OpenAIChatCandidateProvider
from workagent_rsi.workagent_experiment import WorkAgentExperimentRunner
from workagent_rsi.workagent_provider import WorkAgentConfig, WorkAgentSkill


ROOT = Path(__file__).resolve().parents[2]
RESULT_ROOT = ROOT / "results" / "rsi-live-api-20261015"
MODEL = "deepseek-v4-flash"


def _task(task_id: str, domain: str, instruction: str, constraints: dict, hidden: bool = False) -> TaskSpec:
    return TaskSpec(task_id=task_id, domain=domain, instruction=instruction,
                    expected_constraints=constraints, risk_level="low", hidden_test=hidden)


def build_tasks() -> dict[str, list[TaskSpec]]:
    return {
        "develop": [_task(
            "rsi-develop-excel", "excel",
            "Create outputs/rsi_develop.xlsx with worksheet Summary. Put Region in A1, Sales in B1, East in A2, 15 in B2, West in A3, 10 in B3, and =SUM(B2:B3) in B4. Reopen and verify.",
            {"required_sheets": ["Summary"], "required_cells": {"Summary!A1": "Region", "Summary!B2": 15, "Summary!B3": 10}, "required_formulas": {"Summary!B4": "=SUM(B2:B3)"}},
        )],
        "regression": [_task(
            "rsi-regression-word", "word",
            "Create outputs/rsi_regression.docx. Add Heading 1 exactly 'RSI Regression Memo' and a body paragraph exactly 'RSI-REGRESSION-WORD-20261015'. Reopen and verify.",
            {"required_text": "RSI-REGRESSION-WORD-20261015", "required_headings": ["RSI Regression Memo"], "required_heading_styles": {"RSI Regression Memo": "Heading 1"}},
        )],
        "hidden": [_task(
            "rsi-hidden-ppt", "powerpoint",
            "Create outputs/rsi_hidden.pptx with exactly one slide. The title must be exactly 'RSI Hidden Review' and the body must contain exactly 'RSI-HIDDEN-PPT-20261015'. Reopen and verify.",
            {"required_slide_count": 1, "required_shape_text": ["RSI Hidden Review", "RSI-HIDDEN-PPT-20261015"]}, hidden=True,
        )],
        "ood_transfer": [_task(
            "rsi-ood-excel", "excel",
            "Create outputs/rsi_ood.xlsx with worksheet Metrics. Put Item in A1, Value in B1, Alpha in A2, 4 in B2, Beta in A3, 6 in B3, and =SUM(B2:B3) in B4. Reopen and verify.",
            {"required_sheets": ["Metrics"], "required_cells": {"Metrics!A1": "Item", "Metrics!B2": 4, "Metrics!B3": 6}, "required_formulas": {"Metrics!B4": "=SUM(B2:B3)"}},
        )],
    }


def main() -> None:
    RESULT_ROOT.mkdir(parents=True, exist_ok=False)
    api_base = os.environ["OPENAI_BASE_URL"]
    config = WorkAgentConfig(backend="openai-chat", model=MODEL, api_base_url=api_base,
                             timeout_seconds=180, max_tool_turns=10, api_max_retries=4,
                             api_retry_delay_seconds=2.0, verify_com=False)
    provider = OpenAIChatCandidateProvider(model=MODEL, api_base_url=api_base,
                                           timeout_seconds=180, max_retries=4, retry_delay_seconds=2.0)
    initial = WorkAgentSkill(version="1.0.0", instructions=(
        "Follow the current task instruction exactly. Create the requested Office deliverable, reopen it with the "
        "appropriate Python library, assert every requested value, structure, formula, heading, slide text, and "
        "format, then write deliverables.json. Never substitute values from examples for values in the current task."
    ))
    summary = WorkAgentExperimentRunner(workagent_config=config, input_base=ROOT).run(
        build_tasks(), initial, provider, RESULT_ROOT / "experiment", rounds=1
    )
    (RESULT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
