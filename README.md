# WorkAgent-RSI

Benchmark-driven recursive skill improvement for Office agents.

This repository has completed the bounded Phase 3 closed-loop pilot. The Harness, local Office qualification, isolated Codex/Ollama candidate provider, verifier, frozen evaluator, registry, promotion/rollback, and E01-E12 pilot evidence are implemented. This remains a 30-task project-generated pilot, not an external WorkAgent benchmark or powered main study.

## Start here

- [Chinese project overview](docs/project_overview_zh.md)
- [Literature review](docs/literature_review.md)
- [Agent operating contract](Agent.md)
- [Execution plan](project_artifacts/execution_plan.md)
- [Phase 1A design](project_artifacts/phase1_harness/design/harness_architecture.md)
- [Artifact manifest](project_artifacts/artifact_manifest.md)

## Project layout

```text
docs/                         Literature report and preserved sources
project_artifacts/            Phase-gated designs, logs, results and reports
Agent.md                      Agent operating contract and execution gates
tests/                        Single root for automated tests
src/workagent_rsi/             Harness, closed-loop RSI and Office evaluation package
```

## Tooling policy

- Python 3.11+; use `py -3.12` on the current Windows environment.
- `pytest` is allowed and all tests belong under the single top-level `tests/` directory.
- Git is the source-control system; every meaningful phase boundary receives a commit.
- LibreOffice is optional for development but required for claims involving Office recalculation or rendered visual validation.

## Run locally

```powershell
py -3.12 -m pip install -e .
py -3.12 -m pytest -q --basetemp="$env:TEMP\workagent-rsi-tests"
py -3.12 -m workagent_rsi.cli examples/smoke_task.yaml --output run.json
py -3.12 project_artifacts/phase3_experiments/scripts/run_e01_e12.py --provider codex --codex-backend ollama --local-model qwen2.5:7b
```

## Current gate

Phase 1 and Phase 2 are accepted. Phase 3 data quality, Mock B0, Local Office B0, Office COM, Codex/Ollama candidate generation, and all E01-E12 pilot invocations are complete. Results are mechanism-validation evidence for the controlled pilot and must not be reported as an external WorkAgent result or main-study conclusion.
# workagent-rsi
