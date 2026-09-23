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

- `orchestrator-skill`: owns run lifecycle, retries, resume and promotion decisions.
- `gen-skill`: proposes a structured candidate manifest/patch and rationale; it cannot deploy.
- `verify-skill`: performs schema, tool, permission, sandbox, Office-format, security and regression checks.
- `evaluator-skill`: is version-pinned and independently maintained; it computes hard gates and configured quality dimensions.
- `skill-registry`: stores immutable versions, parent links, applicability conditions, evidence and rollback pointers.
- `trace-memory`: stores tasks, tool calls, intermediate state, failures, evaluator outputs and before/after comparisons.
- `executor`: exposes mock and real WorkAgent adapters behind one interface.
- `artifact-store`: content-addressed, append-only storage for inputs, outputs, logs and reports.
- `benchmark-runner`: separates develop, regression, hidden, OOD/transfer and adversarial tasks.
- `promotion-and-rollback`: enforces safety, improvement, non-regression, cost, reproducibility and approval gates.

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
3. Run one minimal task, one complete task and one controlled failure when the adapter is available.
4. Preserve run evidence under `project_artifacts/phase1_harness/logs/`, `results/` and `reports/`.
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
- Phase 3 B0 qualification baseline: completed for the local mock Harness: 25 public tasks, 25 succeeded, 0 failed. This is trace/evaluator plumbing evidence only. The current repository only has a mock adapter and text evaluator; real Office baseline remains blocked on provider/adapter availability.
- Phase 3 Office provider and evaluator qualification: in progress. Formal Office baseline and experiments remain pending until a real executor, format-aware evaluator and environment parity gate are available.
- Phase 3 formal experiments: pending.
