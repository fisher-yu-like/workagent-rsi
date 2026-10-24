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

`Harness.run(task)` remains the normal entry point. Office tasks default to the WorkAgent provider and the shared `ArtifactEvaluator`/`ArtifactVerifier` chain; non-Office smoke tasks keep the basic evaluator. See [`src/workagent_rsi/README.md`](src/workagent_rsi/README.md) for acceptance specs, model review configuration, and the report files written for each run.

```powershell
py -3.12 -m pip install -e .
py -3.12 -m pytest -q --basetemp="$env:TEMP\workagent-rsi-tests"
py -3.12 -m workagent_rsi.cli examples/smoke_task.yaml
py -3.12 project_artifacts/phase3_experiments/scripts/run_b0_office_qualification.py
```

## Current gate

The active local directory is `D:/ws/Projects/WorkAgent-RSI` on the existing
`feat/evaluation-rsi-hardening` branch. See the
[task ledger](project_artifacts/formal_study/hardening_task_ledger.json),
[test/evidence commands](tests/README.md), and
[T04 runtime operations](deploy/agent-runtime/README.md), and
[T05 controlled Office rendering](deploy/office-worker/README.md).
T00-T03 are delivered, including the default-off live-call approval contract.
T04 adds fail-closed native execution, a default Docker backend and an explicit
Apptainer SSH alternative. Qualification status and current tests are recorded in
`project_artifacts/formal_study/hardening_t04_execution_boundary.json`.
T05 adds allowlisted execution/candidate views, source-link checks and verified
copies rendered inside an explicit LibreOffice/Poppler Apptainer worker. Real
XLSX/DOCX/PPTX rendering and owned process cleanup passed; dedicated Microsoft
Office COM remains unavailable. The latest full suite has 512 passed, 2
expected-open failures (R10/R11) and no errors/skips. Evidence is recorded in
`project_artifacts/formal_study/hardening_t15_visibility.json`.
T06 now supplies verified champion and controlled develop history to both candidate
providers; T07 validates complete responses and records every normalization
mapping and transport-owned identity. See [candidate contracts](docs/candidate_generation.md). T08 local validation is delivered with actual behavior acceptance deferred;
T09 now groups comparable results, validates evidence/retries and formal claim
boundaries, and writes separate paired reference runs. See [result cohorts](docs/result_cohorts.md).
T10 adds [reviewed task requirement coverage](docs/requirement_admission.md);
T11 adds [registered check preflight](docs/check_registry.md); T12 adds
[scoped Office content checks](docs/scoped_content_checks.md). Legacy v1 scores
remain declared-check compatibility, with no reviewed task score; T17 migration
is pending. T14 adds [authorized edit preservation](docs/edit_preservation.md).
T13 adds [formula/recalculation evidence](docs/formula_recalculation.md), and
T15 adds [visibility risks and page coverage](docs/visibility_checks.md). Their
local work is complete; real T13/T15 qualification remains deferred. R01-R09
and R12 pass, including conservative gap/review outcomes for R03-R05; R10/R11
remain open. T16 onward and the overall G1 gate remain pending, along with
T08 real behavior acceptance. Historical T01 red
observations are retained; their repair status must be read from the latest
ledger rather than the original red baseline. The historical gate summary follows.

Phase 1 and Phase 2 are accepted. Phase 3 data quality, local Office qualification, candidate generation, and the historical E01-E12 pilot are complete. The historical pilot is mechanism-validation evidence over a project-generated fixture, not an external WorkAgent result or main-study conclusion.

The guarded formal entry point is
`project_artifacts/phase3_experiments/scripts/run_formal.py`. Use `--mode pilot` for
the local fixture; `--mode formal` stays closed until source-specific license,
checksum, provenance and quality checks are recorded.
# workagent-rsi
