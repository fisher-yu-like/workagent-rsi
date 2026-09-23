# WorkAgent-RSI

Benchmark-driven recursive skill improvement for Office agents.

This repository is currently in Phase 1B. The local mock Harness pipeline is implemented and validated; a real external WorkAgent integration has not been claimed.

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
tests/                        Single root for automated tests (Phase 1B)
src/workagent_rsi/             Implementation package (Phase 1B)
```

## Tooling policy

- Python 3.11+; use `py -3.12` on the current Windows environment.
- `pytest` is allowed and all tests belong under the single top-level `tests/` directory.
- Git is the source-control system; every meaningful phase boundary receives a commit.
- LibreOffice is optional for development but required for claims involving Office recalculation or rendered visual validation.

## Run locally

```powershell
py -3.12 -m pip install -e .
py -3.12 -m pytest -q --basetemp=.pytest-tmp
py -3.12 -m workagent_rsi.cli examples/smoke_task.yaml --output run.json
```

## Current gate

The local mock pipeline is complete. Phase 1B remains open for a concrete WorkAgent provider and real Office task execution; Phase 2 must not start before the Phase 1 gate is accepted.
