# WorkAgent-RSI

WorkAgent-RSI helps an Office assistant complete a task, check the generated file, and keep a verified improvement for later tasks. The normal entry point is `Harness`; one run produces one result directory under `project_artifacts/results/`.

The project keeps the full research machinery behind a small vocabulary: `Run` executes, `Learn` exports an isolated workspace and proposes a bounded improvement, `Check` verifies/evaluates/promotes, and `Store` keeps the evidence and version history. Candidate isolation, leakage checks, frozen evaluation, promotion and rollback remain available through these facades and the compatible internal modules.

## Start here

- [当前 LLM 任务评估协议](docs/operations/llm-task-review.md)（2026-10-29）
- [本次改造与验证记录](docs/operations/llm-task-review-migration-20261029.md)
- [历史评估与 RSI 执行记录](docs/operations/evaluation-rsi-v2.md)

- [Chinese project overview](docs/project_overview_zh.md)
- [Literature review](docs/literature_review.md)
- [Agent operating contract](Agent.md)
- [Execution plan](project_artifacts/execution_plan.md)
- [Phase 1A design](project_artifacts/phase1_harness/design/harness_architecture.md)
- [Artifact manifest](project_artifacts/artifact_manifest.md)

## Project layout

```text
docs/                         Literature report and preserved sources
project_artifacts/results/    All new run output, one directory per run
project_artifacts/            Phase-gated designs and archived evidence
Agent.md                      Agent operating contract and execution gates
tests/                        Single root for automated tests
src/workagent_rsi/             Harness, closed-loop RSI and Office evaluation package
```

## Tooling policy

- Python 3.11+; the current verified Windows environment uses `.venv\Scripts\python.exe` (Python 3.13).
- `pytest` is allowed and all tests belong under the single top-level `tests/` directory.
- Git is the source-control system; every meaningful phase boundary receives a commit.
- LibreOffice is optional for development but required for claims involving Office recalculation or rendered visual validation.

## Run locally

`Harness.run(task)` remains the normal entry point. Office tasks default to the WorkAgent execution provider. Artifact evaluation uses one task-level LLM review through `SharedAssessment`, with report adapters `ArtifactEvaluator` and `ArtifactVerifier`. See [`src/workagent_rsi/README.md`](src/workagent_rsi/README.md) for original-task input, model review configuration, and the report files written for each run.

```powershell
py -3.12 -m pip install -e .
py -3.12 -m pytest -q --basetemp="$env:TEMP\workagent-rsi-tests"
py -3.12 -m workagent_rsi.cli examples/smoke_task.yaml
py -3.12 project_artifacts/phase3_experiments/scripts/run_b0_office_qualification.py
```

## Current evaluation protocol

On 2026-10-29 the user changed the evaluation direction: the LLM judges task
reasonableness, artifact completion, quality and defects from the original task
and supplied evidence. Code reads files, renders pages, executes calculations,
calls the model and records results. Task-specific acceptance rules, registered
checks and weighted rescoring have been removed from the active path.

The artifact repair loop and the skill improvement loop use the same assessment
protocol. Skill edit boundaries, execution isolation, budgets, paired comparison,
versioning and rollback remain enforced. With no configured judge, quality stays
unknown and the assessment is incomplete. Real model calls require an approved
configuration and budget.

See the [current protocol](docs/operations/llm-task-review.md),
[migration report](docs/operations/llm-task-review-migration-20261029.md), and
[task ledger](project_artifacts/formal_study/hardening_task_ledger.json).
Old experiments retain their original evaluator identity. Their scores do not
qualify the new protocol; live model accuracy and new research comparisons
remain unverified. The historical 140 uncovered code-rule units are no longer
an implementation backlog.
