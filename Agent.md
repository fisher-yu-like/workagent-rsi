# WorkAgent-RSI Agent Operating Contract

## Project

WorkAgent-RSI is a benchmark-driven recursive skill improvement framework for Office agents. In this repository, RSI means **Recursive Skill Improvement**. It does not mean unrestricted model-weight self-modification.

## Non-negotiable execution rules

1. Treat the repository as evidence-first. Distinguish design, implemented code, actual run results, unverified assumptions and blockers.
2. Do not fabricate WorkAgent traces, datasets, scores, screenshots, Office files or successful pipeline runs.
3. Preserve user changes and do not use destructive Git commands.
4. Record every run command, working directory, Git commit, environment/dependency versions, configuration, timestamps, stdout/stderr, exit code, generated files and evaluator output.
5. Keep all automated tests under one top-level `tests/` directory. `pytest` is allowed; do not create phase-specific test trees under `project_artifacts/`.
6. Use `py -3.12` or an explicit Python 3.11+ environment; do not rely on the legacy default `python` command.
7. Office deliverables must be real `.pptx`, `.docx` and `.xlsx` files readable by their corresponding libraries. Markdown or renamed text is not an Office artifact.
8. Candidate skills may not modify the evaluator, hidden tests, promotion policy, protected artifacts or safety allowlist.
9. Keep Markdown/JSON/CSV evidence alongside binary artifacts for inspection and versioning.
10. Only one primary task may be `in_progress` in `project_artifacts/execution_plan.md`.

## Architecture principles

The user-facing architecture uses six short names:

- `Harness`: the only normal entry point; starts a run, returns its result and can resume a saved trace.
- `Run`: executes a task, calls the selected adapter and creates the Office artifact.
- `Learn`: exports an isolated workspace, diagnoses observed failures and proposes a bounded candidate change.
- `Check`: independently verifies candidates, evaluates artifacts or frozen splits and applies promotion gates.
- `Store`: keeps artifacts, traces, immutable skill versions, lineage, champion aliases and rollback records.
- `Data`: contains the validated task, change, report and version records.

The older files remain internal compatibility modules. Their responsibilities still stay separate: candidate generation cannot deploy, verification cannot change evaluator rules, the frozen evaluator cannot be changed by a candidate, and promotion cannot rewrite historical evidence. The shorter names reduce the number of concepts a user must learn; they do not remove any safety or evaluation function.

## Three-stage project execution plan

### Stage 1: Harness design and pipeline execution

#### Phase 1A: Design gate

1. Audit repository and environment.
2. Define Harness components, interfaces, state lifecycle, safety boundaries and observability.
3. Define normal, failure, retry and resume pipeline paths.
4. Define unit, integration, end-to-end and Office adapter tests.
5. Update `project_artifacts/execution_plan.md` and `project_artifacts/artifact_manifest.md`.
6. Stop and wait for user approval. Do not implement or run the real pipeline before approval.

#### Phase 1B: Implementation and evidence

1. Implement typed contracts, storage, allowlisted tools, mock adapter and orchestrator.
2. Run static checks, unit tests, integration tests, smoke test and end-to-end test.
3. Run normal successful tasks through the public `Harness` entry point. Use a naturally observed failure or a dedicated unit test only when failure behavior is being investigated.
4. Preserve new run evidence under `project_artifacts/results/`; historical phase directories remain read-only archives.
5. Generate Office reports only from actual results and validate them with corresponding libraries.
6. Stop at the Stage 1 acceptance gate and wait for user confirmation.

### Stage 2: RSI framework and training plan

Only after Stage 1 acceptance:

1. Define RSI scope and relation to Harness/WorkAgent.
2. Design data, trace, sample selection, training/optimization, evaluation, feedback, registry, rollback and safety modules.
3. Produce the training plan, experiment matrix, resource budget and design reports.
4. Do not describe unexecuted training as a result.
5. Stop and wait for user approval before Stage 3.

### Stage 3: Dataset and experiments

Only after Stage 2 acceptance:

1. Identify datasets with official sources, licenses, versions, fields and leakage risks.
2. Download or construct data reproducibly, preserving raw/interim/processed/train/validation/test layers.
3. Run quality checks and produce dataset provenance reports.
4. Run baseline first, then prioritized experiments with fixed seeds, configs, logs, checkpoints and real evaluator outputs.
5. Generate final reports and valid Office artifacts, clearly separating completed, running, failed and not-started experiments.

## Promotion policy

A candidate skill version can be promoted only if all conditions hold:

- critical safety and format gates pass;
- no forbidden tool, permission or evaluator modification is introduced;
- develop score improves beyond the configured noise tolerance;
- protected regression tasks do not have critical failures;
- hidden/OOD performance has no unacceptable regression;
- resource increase is justified by measured gain;
- the run is reproducible from immutable inputs/configuration;
- high-risk changes receive human approval;
- parent version, diff, rationale and evidence are stored.

## Current state

- Literature review: completed for the two specified arXiv works.
- Phase 1A design: completed and approved.
- Phase 1B local mock pipeline: implemented and validated.
- Phase 1B accepted by the user with the external WorkAgent limitation recorded.
- Phase 2 RSI framework and training plan: completed and approved on 2026-09-23.
- Phase 3 dataset catalog and quality gate: completed for the project-generated pilot fixture. It must not be described as an external benchmark.
- Phase 3 B0 qualification baseline: completed for the local mock Harness: 25 public tasks, 25 succeeded, 0 failed. This is trace/evaluator plumbing evidence only and is separate from the local Office provider qualification below.
- Phase 3 Office provider and evaluator qualification: completed for the local executor. LocalOfficeAdapter, OfficeArtifactEvaluator and Word/Excel/PowerPoint 16.0 COM reopening passed 25/25 public tasks.
- Phase 3 closed-loop infrastructure: completed with isolated candidate workspaces, deterministic diagnosis, Codex CLI plus local Ollama provider, leakage critic, fail-closed verifier, frozen evaluator, immutable registry, promotion controller and rollback.
- Phase 3 E01-E12 pilot: completed on the 30-task project-generated fixture. All result claims remain pilot-only; E07 is automated artifact-versus-response cross-evaluation with no human-label claim.
- Simple public Harness API: available through `workagent_rsi.Harness`; normal runs use the task's required text and write all new evidence below `project_artifacts/results/`.
- Formal execution roadmap: approved for automatic execution on 2026-09-27; human-readable live log is `project_artifacts/execution_log.md`.
- Stage 0 baseline freeze: completed on 2026-09-27 at commit `21f482ae9ab1d80b9f7cc4518f62e8ad9a8aeb95`; 61 tests passed, compileall passed, 14 pilot data-quality checks passed, Office 16.0 COM was available for all three applications, LibreOffice was unavailable, and no external WorkAgent result is claimed.
- Stage 1 real Office provider upgrade: completed on clean commit `3de1ecd3c3ce28f3e6f0ea50b811bb6ce58fd04a`; COM qualification passed 25/25 public tasks across Excel, Word and PowerPoint, with zero automation Office processes remaining. Interruption and cleanup evidence is in `project_artifacts/formal_study/stage1_manifest.json`.
- Current primary task: Stage 2 file-level automatic evaluator v2. The agent must append progress and evidence to `project_artifacts/execution_log.md` before moving to the next stage.
