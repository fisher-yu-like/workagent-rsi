# WorkAgent-RSI Closed-Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Complete the remaining bounded RSI pilot infrastructure, run evidence-backed E01-E12 pilot experiments with a local Codex provider where required, and publish a Chinese project overview.

**Architecture:** Add focused modules for records, diagnosis, candidate isolation/provider execution, leakage verification, frozen evaluation, registry, promotion, and experiments. Candidate generation runs in standalone workspaces; protected data and evaluator/governance files remain outside those workspaces. Experiments use real artifacts and explicit failed/unavailable states rather than synthetic success.

**Tech Stack:** Python 3.12, Pydantic 2, SQLite, pytest, openpyxl, python-docx, python-pptx, PowerShell Office COM validation, Codex CLI 0.144.2, Git.

**Spec:** docs/superpowers/specs/2026-09-24-workagent-rsi-closed-loop-design.md

## Global Constraints

- All tests remain directly under the single top-level tests directory.
- Candidate workspaces cannot contain hidden tasks, evaluator code, promotion thresholds, protected evidence, or credentials copied by the project.
- Candidate code cannot modify evaluator, hidden tests, promotion policy, safety allowlist, registry history, or prior evidence.
- E07 is automated artifact-evaluator versus response-judge cross-evaluation and makes no human-label claim.
- The 30-task dataset is pilot evidence only.
- Use py -3.12 for Python commands.
- Every experiment records real status and evidence; missing capability never becomes a score.

---

### Task 1: RSI Records and Canonical Hashing

**Files:**
- Create: src/workagent_rsi/rsi_contracts.py
- Create: src/workagent_rsi/hashing.py
- Test: tests/test_rsi_contracts.py

**Interfaces:**
- Produces Pydantic models CandidatePatch, AtomicEdit, FailureDiagnosis, VerificationReport, SkillVersion, PromotionDecision, EvaluationContract, ProviderRecord, ExperimentResult.
- Produces sha256_bytes, sha256_file, canonical_json_hash.

- [ ] Write tests that reject unknown fields, invalid decisions/statuses, empty evidence references, and non-relative edit targets.
- [ ] Run the tests and verify collection fails because the module is absent.
- [ ] Implement the minimal models and canonical hashing helpers.
- [ ] Run tests and the existing contract suite.
- [ ] Commit the records layer.

### Task 2: Deterministic Failure Diagnosis

**Files:**
- Create: src/workagent_rsi/diagnosis.py
- Test: tests/test_diagnosis.py

**Interfaces:**
- Produces FailureDiagnoser.diagnose(run_results, evidence_refs) -> list[FailureDiagnosis].
- Consumes public run results only.

- [ ] Write failing tests for format, semantic, tool, evaluator, safety, and successful-run exclusion.
- [ ] Implement deterministic classification with evidence references and stable diagnosis IDs.
- [ ] Verify repeated input produces identical diagnoses.
- [ ] Commit the diagnosis component.

### Task 3: Isolated Candidate Workspace

**Files:**
- Create: src/workagent_rsi/candidate_workspace.py
- Test: tests/test_candidate_workspace.py

**Interfaces:**
- Produces CandidateWorkspaceBuilder.export(source_root, workspace_root, allowed_files, context_files).
- Produces CandidateWorkspaceManifest with file hashes and excluded protected paths.

- [ ] Write failing tests for allowlisted copies, symlink rejection, traversal rejection, hidden/evaluator exclusion, and standalone Git initialization.
- [ ] Implement copy-by-allowlist and generated candidate AGENTS.md policy.
- [ ] Verify no protected basename or source path leaks into the workspace manifest.
- [ ] Commit candidate isolation.

### Task 4: Candidate Providers

**Files:**
- Create: src/workagent_rsi/candidate_provider.py
- Create: project_artifacts/phase3_experiments/provider/candidate_patch.schema.json
- Create: project_artifacts/phase3_experiments/provider/candidate_prompt.md
- Test: tests/test_candidate_provider.py

**Interfaces:**
- Defines CandidateProvider protocol.
- Provides DeterministicCandidateProvider for tests.
- Provides CodexCandidateProvider.generate(workspace, diagnosis, parent_version, edit_budget) -> CandidatePatch plus ProviderRecord.

- [ ] Write failing tests for command construction, output-schema use, timeout, nonzero exit, invalid JSON, schema mismatch, and successful parsing.
- [ ] Implement subprocess execution with codex exec, ephemeral mode, workspace-write sandbox, JSONL logs, and bounded timeout.
- [ ] Ensure provider logs never expose environment secrets.
- [ ] Commit provider integration.

### Task 5: Leakage Critic and Verifier

**Files:**
- Create: src/workagent_rsi/leakage.py
- Create: src/workagent_rsi/verifier.py
- Test: tests/test_leakage.py
- Test: tests/test_verifier.py

**Interfaces:**
- LeakageCritic.scan(candidate, protected_fingerprints, protected_paths) -> findings.
- CandidateVerifier.verify(candidate, workspace, policy) -> VerificationReport.

- [ ] Write failing tests for protected IDs, answer fragments, evaluator/governance path edits, absolute paths, task-specific maps, and clean patches.
- [ ] Write failing tests proving verifier ordering and fail-closed behavior.
- [ ] Implement schema, path, leakage, compile, pytest, smoke, Office reopen, timeout, and evidence checks.
- [ ] Verify a critical finding prevents later execution.
- [ ] Commit verification components.

### Task 6: Immutable Registry, Promotion, and Rollback

**Files:**
- Create: src/workagent_rsi/registry.py
- Create: src/workagent_rsi/promotion.py
- Test: tests/test_registry.py
- Test: tests/test_promotion.py

**Interfaces:**
- SkillRegistry.register, get, lineage, champion, set_champion, record_rejection.
- PromotionController.decide(champion_report, candidate_report, verification, contract).
- RollbackManager.rollback(target_version, evidence_refs).

- [ ] Write failing tests for immutable versions, duplicate hash behavior, parent lineage, transactional alias changes, and rollback.
- [ ] Write failing tests for every non-compensatory promotion gate and missing evidence.
- [ ] Implement SQLite index plus content-addressed package storage.
- [ ] Commit registry and governance.

### Task 7: Skill-Aware Office Execution and Frozen Evaluation

**Files:**
- Create: src/workagent_rsi/skill_runtime.py
- Create: src/workagent_rsi/frozen_evaluator.py
- Test: tests/test_skill_runtime.py
- Test: tests/test_frozen_evaluator.py

**Interfaces:**
- PilotSkillConfig controls marker_source and domain applicability.
- SkillConfiguredOfficeAdapter produces genuine Office artifacts from a SkillVersion.
- FrozenEvaluator evaluates explicit split manifests under EvaluationContract and returns sealed aggregate reports.
- ResponseJudge evaluates response/instruction evidence independently of Office package reopening.

- [ ] Write failing tests showing the baseline task_id marker fails required-text tasks and the constraint marker passes.
- [ ] Write failing tests for split hash mismatch, evaluator hash mismatch, hidden per-task redaction, and automated evaluator agreement.
- [ ] Implement actual DOCX/XLSX/PPTX execution and aggregate scoring.
- [ ] Commit runtime and evaluator.

### Task 8: Closed-Loop Coordinator and Experiment Runner

**Files:**
- Create: src/workagent_rsi/rsi_loop.py
- Create: src/workagent_rsi/experiment_runner.py
- Create: project_artifacts/phase3_experiments/scripts/run_e01_e12.py
- Test: tests/test_rsi_loop.py
- Test: tests/test_experiment_runner.py

**Interfaces:**
- RSILoop.run_round orchestrates diagnosis, generation, verification, evaluation, registry, and promotion.
- ExperimentRunner.run(experiment_id, provider, output_root) creates an immutable invocation.

- [ ] Write a failing fake-provider end-to-end test covering promotion and rollback.
- [ ] Write failing experiment tests for completed, failed, unavailable, and blocked states plus resume identity.
- [ ] Implement E01-E12 arm configuration from experiment_matrix.csv.
- [ ] Implement E07 automated cross-evaluation and E11 adversarial leakage fixture.
- [ ] Commit the closed loop and experiment runner.

### Task 9: Real Provider and Pilot Evidence

**Files:**
- Create: project_artifacts/phase3_experiments/results/codex_provider_smoke/<invocation>/
- Create: project_artifacts/phase3_experiments/results/e01_e12/<invocation>/
- Update: project_artifacts/execution_plan.md
- Update: project_artifacts/artifact_manifest.md

- [ ] Run the real Codex provider smoke in an isolated workspace.
- [ ] Validate the returned candidate schema and provider record.
- [ ] Run E01-E12 with fixed pilot contracts and real status recording.
- [ ] Re-run mock B0, local Office B0, and Office COM qualification.
- [ ] Preserve all failures, unavailable channels, costs, logs, hashes, and decisions.
- [ ] Commit code-generated evidence separately from implementation commits.

### Task 10: Overall Documentation

**Files:**
- Create: docs/project_overview_zh.md
- Update: README.md
- Update: Agent.md
- Update: project_artifacts/phase3_experiments/README.md

- [ ] Document research basis, implemented architecture, real skill/provider addresses, data flow, security boundaries, commands, E01-E12 outcomes, evidence locations, limitations, and next steps.
- [ ] Explicitly distinguish local qualification, Codex-backed provider evidence, automated E07 cross-evaluation, and unperformed main study.
- [ ] Verify every result statement points to an evidence file.
- [ ] Commit documentation.

### Task 11: Final Verification and GitHub Delivery

**Files:**
- Verify all changed files and evidence roots.

- [ ] Run py -3.12 -m compileall over src, tests, and experiment scripts.
- [ ] Run the complete pytest suite with an external basetemp.
- [ ] Run dataset quality checks.
- [ ] Run git diff --check and scan for secrets, placeholders, error cells, and stale claim language.
- [ ] Confirm no Office process created by the project remains running.
- [ ] Remove repository-local caches without touching user files.
- [ ] Commit final evidence/doc updates.
- [ ] Push codex/closed-loop-rsi to origin and report the remote branch.
