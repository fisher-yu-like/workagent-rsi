# WorkAgent-RSI

WorkAgent-RSI helps an Office assistant complete a task, check the generated file, and keep a verified improvement for later tasks. The normal entry point is `Harness`; one run produces one result directory under `project_artifacts/results/`.

The project keeps the full research machinery behind a small vocabulary: `Run` executes, `Learn` exports an isolated workspace and proposes a bounded improvement, `Check` verifies/evaluates/promotes, and `Store` keeps the evidence and version history. Candidate isolation, leakage checks, frozen evaluation, promotion and rollback remain available through these facades and the compatible internal modules.

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
project_artifacts/results/    All new run output, one directory per run
project_artifacts/            Phase-gated designs and archived evidence
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
py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/readme
py -3.12 -m workagent_rsi.cli examples/smoke_task.yaml
py -3.12 project_artifacts/phase3_experiments/scripts/run_b0_office_qualification.py
```

For a real Office run, save a task YAML beside any input files it names. For example,
`office_task.yaml` can contain:

```yaml
task_id: monthly-report
domain: excel
instruction: Edit the supplied workbook into a monthly summary with clear headings.
input_files:
  - source.xlsx
```

Then run `py -3.12 -m workagent_rsi.cli office_task.yaml --execution-provider workagent`.
The `source.xlsx` path is resolved from `office_task.yaml`'s directory, not the
shell's current directory. The provider flag is optional for Office tasks:
`excel`, `word`, and `powerpoint` domains use WorkAgent by default. A `smoke`
task uses the smoke provider by default. Supported Office inputs and outputs
are `.xlsx` for Excel, `.docx` for Word, and `.pptx` for PowerPoint; formats
must match the task domain.

WorkAgent uses the local Codex CLI with Ollama `qwen2.5:7b` by default. It does
not fall back to a template when the model is unavailable or fails. Its
`workspace-write` sandbox is not verified to prevent reads outside the task
workspace and is not a strong isolation boundary for sensitive inputs. Until
that limit is resolved, use only non-sensitive, project-generated inputs.

## Current gate

Phase 1 and Phase 2 are accepted. Phase 3 data quality, local Office qualification, candidate generation, and the historical E01-E12 pilot are complete. The historical pilot is mechanism-validation evidence over a project-generated fixture, not an external WorkAgent result or main-study conclusion.

The guarded formal entry point is
`project_artifacts/phase3_experiments/scripts/run_formal.py`. Use `--mode pilot` for
the local fixture; `--mode formal` stays closed until source-specific license,
checksum, provenance and quality checks are recorded.

The generic WorkAgent six-task qualification is separate from the older B0/local
Office executor and historical E05 RSI fixture. Its first and second real
Codex/Ollama `qwen2.5:7b` invocations both passed **0/6** tasks: [first
evidence](project_artifacts/results/qualification/general-office/20260929T190856Z-ab3365c5/)
and [second evidence](project_artifacts/results/qualification/general-office/20260929T195704Z-a4674234/).
No deliverable Office files were produced, so artifact evaluation and COM reopen
could not establish success. The [RSI preflight report](project_artifacts/results/qualification/general-office/20260929T210812Z-e0610074/qualification_report.md)
freezes the 12-task project-generated matrix and blocks before any WorkAgent or
candidate call. Failure/unavailable is not a score, and none of these runs is
an external benchmark result. A qualifying create/edit pair for each format
remains necessary before RSI may start.
# workagent-rsi
