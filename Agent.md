# WorkAgent-RSI Agent Operating Contract

## Project

Current hardening status (2026-10-26): see [execution and handoff](docs/operations/evaluation-rsi-v2.md) and the [task ledger](project_artifacts/formal_study/hardening_task_ledger.json). T28 has32 first-pass provisional labels and6 actual nonblind adjudications (3FAIL/3INCOMPLETE);2 controlled-reference interpretations still differ. Original labels remain unchanged. Complete judge calibration remains pending. The v1 standard pilot stopped on request6 with HTTP429, without retry. The prior engineering snapshot passed Windows773 and selected Linux non-COM149 checks. Later preparation freezes judge v2 requests and72 unreviewed T31 spec drafts, with focused validation only. New v2 model approval is pending; no new model/server calls were made during adjudication intake. Real four-arm dispatch still requires a qualified token-metered backend. Historical phase results below do not establish these later acceptance claims.

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

For current hardening work, use `project_artifacts/formal_study/hardening_task_ledger.json`
and `hardening_t27_offline_calibration.json` / `hardening_t28_human_calibration.json`. Work in the existing
`feat/evaluation-rsi-hardening` branch at `D:/ws/Projects/WorkAgent-RSI`.
T00-T03 are delivered; T03 includes the strict default-off live-call policy.
T04's default Docker and explicit Apptainer SSH backends do not execute native
model scripts on the host. Read the T04 manifest for actual backend qualification;
CLI-owned sandbox capability must remain separate. R01-R12 pass; T21/T22 now close the task-local repair gap. T05 now isolates execution/candidate views and
hash-verified rendering copies. LibreOffice/Poppler rendering, unrelated-instance
survival and timeout cleanup passed on the explicit Apptainer worker; dedicated
Microsoft Office COM remains unavailable. See `deploy/office-worker/README.md`.
T06 shares verified champion/develop context across API/CLI; public history and
context budgets are checked offline. See `docs/candidate_generation.md`.
T07 admits complete raw candidate responses with auditable normalization and
transport-owned model identity. Both tasks were qualified offline only.
The latest full suite has 717 passed with no failures, errors or skips.
The final T23/T24 focused suite has 129 passes; T21/T22 historical focused has121.
T20's focused suite has 114 passes; the real-probe visual scope repair has 84.
Counts and evidence are recorded in the task ledger. T08 actual isolated behavior and
RSI rejection passed on frozen CLI-generated Office programs; champion was unchanged.
This is authored qualification, not a full live RSI benchmark. See `docs/candidate_verification.md`. T09 comparable-cohort
analysis and reference evaluation are complete offline; see `docs/result_cohorts.md`.
T10 adds task-bound reviewed requirement coverage, T11 preflights registered checks,
and T12 enforces scoped positions with separate requested/observed evidence. See
`docs/requirement_admission.md`, `docs/check_registry.md`, `docs/scoped_content_checks.md`.
T17 now unifies normal Check/Harness/RSI task evaluation with reviewed admission
and explicit task/quality/coverage outcomes. Legacy v1 fields remain declared-check
compatibility only; historical task entrypoints require an explicit legacy profile.
T14 structural edit preservation is delivered within its documented support.
T13 formula/recalculation and T15 geometry/page-coverage local work are complete;
T13 actual qualification passed14 frozen LibreOffice worker runs. T15 actual rendering
and individual controls passed; a real long-deck scope issue was fixed in0b64a04.
Its separately approved three-request real recheck passed: two readable batches
accepted, last-page defect rejected, all17 pages covered.
See `docs/edit_preservation.md`, `docs/formula_recalculation.md` and
`docs/visibility_checks.md`. T16 adds scoped/source-bound evidence partitions and
independent review records. Actual CLI semantic/source/injection/cache/independent and
joint-image controls passed. Direct API /responses and accuracy calibration remain
unqualified; the configured CLI and corrected real batch-scope probes passed. T18 adds
grounded issue facts, repair targets and verification steps; general feedback no
longer contains internal fixture knobs. See `docs/judge_evidence_scope.md`,
`docs/score_semantics_v2.md` and `docs/issue_evidence_quality.md`.
T19 trace-grounded hypotheses, private-trace protection and five genuine authored
local failure probes passed, with 51 focused tests. T20 makes valid execution
failures learnable, retains null unobserved artifact quality, preserves fixed
task denominators and distinguishes transport/environment/input gaps. R11 now
passes and actual RSI capture receives syntax-failure feedback. See
`docs/trace_diagnosis.md` and `docs/execution_failure_feedback.md`.
T21 adds opt-in task-local repair with fresh full assessment and frozen task/skill.
T22 adds shared reservations for native model/tool calls, retries, judge calls and
API candidate generation, best-result retention, scoped output edits and protected
split isolation. Failed and interrupted requests stay charged. Environment gaps
retain earlier files while keeping outcomes incomplete. Execution/candidate CLI
loops are unavailable under a bounded runtime budget because their internal calls
cannot be reserved; the read-only judge CLI remains metered per invocation.
See `docs/artifact_repair.md`. T23 removes fixture answer rules and task-ID
strategy selection, adds explicit task mode and qualification-only formal guards.
T24 adds optional sandbox input inspection, facts separate from declared plans,
and independent variant oracles. Its authored local program passed22 actual
Office cases in nine groups, including unchanged-code and randomized-ID controls.
This qualifies local engineering and that authored implementation; it does not
establish current model/champion generalization or new real sandbox qualification.
Earlier T24 SSH forwarding refused the connection. It is now restored; actual
T26 boundary and T28 rendering passed. No new model requests were made. See `docs/input_behavior_probes.md`
and `docs/policies/template-and-overfitting.md`. T00-T25 engineering tasks are
delivered. T26 local family/source/variant and one-use final-store interfaces pass;
its 72-base/216-instance corpus and separate evaluator deployment remain blocked.
T25 supplies 90 exposed calibration cases, 30 inputs and 3 source families. The
calibration-splits profile covers 23 checks; complete handoff regression remains
mandatory. T27 deterministic calibration is delivered:45 PASS/28 FAIL/17 INCOMPLETE over90 cases;
2 visual defects remain unresolved, not passed. T28 local human provenance/UI and
12 actual server renders/20 pages are complete; actual user labels,20 natural
artifacts and newly bounded judge calls remain pending. User will provide independent
files later and asked to stop after this delivery without new material generation.
T26 actual candidate-mount denial is qualified; separate principals remain unprovisioned.
T29-T35 and later live/research qualification remain unfinished. All-green local tests and authored
probes do not establish live model repair or RSI improvement.
The entries below preserve historical stage evidence.

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
- Stage 2 file-level automatic evaluator v2: completed on commit `ab37c71aa00f288f9a6f5be2b708007e9f405189`; evaluator-v2 validation passed for Excel/Word/PowerPoint, COM qualification passed 25/25, and pixel rendering remains explicitly unavailable rather than scored.
- Stage 3 six-round RSI code is implemented and covered by tests: budgets `[3, 3, 2, 2, 1, 1]`, atomic checkpoints, identity validation on resume, immutable completed rounds, inherited evidence, registry negative evidence and explicit unavailable cost channels.
- Stage 3 six-round qualification: completed on commit `312a61caa447af91eafe9180ffa5d183f7166759`; deterministic E05 ran six rounds with one accepted improvement, one rejection and four negative-evidence prunes; interrupted-resume and champion inheritance tests passed; full suite reports 72 passed.
- Current primary task: preserve the external dataset/source/license/quality gate while qualifying the real local-model RSI provider. The metadata-only gate, guarded formal matrix, fail-closed analyzer and checksum-verified downloader are implemented; no external task files have entered formal results. The real-model E05 pilot is complete and recorded in `project_artifacts/formal_study/stage5_manifest.json`; until an official file-level license and provenance are verified, it remains project-generated engineering evidence only. The agent must append progress and evidence to `project_artifacts/execution_log.md` before moving to the next stage.
- Stage 4 current commands: `quality_check_external.py` validates the metadata boundary; `run_formal.py --mode formal` refuses to create results while `formal_dataset_selected` is null; `run_formal.py --mode pilot` writes only project-generated qualification evidence; `analyze_formal.py` excludes unavailable and timeout channels from numeric aggregates.
- Stage 4 pilot matrix: deterministic E01/E02/E05/E07/E08/E12 completed 6/6 with no unavailable or failed runs; this remains project-generated engineering evidence and does not authorize an external benchmark claim.
- Stage 5 real-model RSI pilot: Codex CLI `0.158.0-alpha.2.1` with Ollama `qwen2.5:7b` completed E05 in six rounds on 2026-09-28. One candidate was accepted and five were rejected; develop moved from 0.0 to 1.0. The run is explicitly project-generated, `claims_allowed=false`, and is not model-weight training or an external benchmark result. Full evidence is in `project_artifacts/formal_study/stage5_manifest.json` and `project_artifacts/formal_study/stage5_real_model_report.md`.
