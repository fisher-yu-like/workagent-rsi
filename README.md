# WorkAgent-RSI

Benchmark-driven recursive skill improvement for Office agents.

This repository is currently at the Phase 3 formal-experiment gate. The mock Harness, RSI design, pilot dataset, and local Office provider/evaluator qualification are implemented and validated. A real external WorkAgent integration and E01-E12 experiment results have not been claimed.

## Start here

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
src/workagent_rsi/             Harness and local Office qualification package
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
```

## Current gate

Phase 1 and Phase 2 have been accepted. The Phase 3 pilot dataset, mock B0 qualification, and local Office provider/evaluator qualification are complete. Formal E01-E12 experiments remain pending until an external WorkAgent/candidate generator is configured; local qualification evidence must not be reported as an RSI experiment result.
