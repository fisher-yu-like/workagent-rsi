# WorkAgent-RSI

Benchmark-driven recursive skill improvement for Office agents.

This repository is currently at the Phase 1A design gate. The literature report and Harness/Pipeline design are complete; implementation and real pipeline execution have not been claimed.

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

## Current gate

Phase 1A is waiting for user approval. Do not start Phase 1B until the design gate is explicitly approved.

