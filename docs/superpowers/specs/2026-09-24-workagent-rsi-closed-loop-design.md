# WorkAgent-RSI Closed-Loop Implementation Design

## Status and approval

This specification records the user-approved architecture for completing the remaining WorkAgent-RSI pilot infrastructure. Approval was given on 2026-09-24 to use the locally authenticated Codex CLI as the candidate provider. The provider is reported as a Codex-backed local provider, not as an external WorkAgent product.

The implementation is evidence-first. Missing provider output, failed Office execution, absent human labels, or incomplete protected evaluation remains unavailable, failed, blocked, or pending. No component may synthesize a successful score or promotion decision from missing evidence.

## Goal

Build and execute a bounded, reproducible recursive skill-improvement loop for the existing 30-task Office pilot. The system diagnoses public-task failures, generates candidate skill patches in isolated workspaces, verifies patches independently, evaluates permitted splits with frozen policies, maintains immutable skill versions, promotes or rejects candidates through non-compensatory gates, supports rollback, records E01-E12 pilot outcomes, and produces a Chinese overall project introduction.

## Claim boundary

- The 30-task dataset supports a pilot and infrastructure qualification, not a statistically powered main-study claim.
- Local Codex CLI generation is a real model-backed provider execution, but it is not an external WorkAgent product.
- LocalOfficeAdapter is a deterministic Office artifact provider, not a general-purpose Office agent.
- Hidden task content is evaluator-only. Candidate generation receives no hidden IDs, prompts, expected values, or per-task feedback.
- E07 requires independent human labels. Without them, the system creates an audit bundle and marks the experiment pending_human_audit. A model review cannot be relabeled as human audit.
- Provider or infrastructure failure produces unavailable, failed, or blocked, never an imputed score.

## Non-goals

- Model-weight training or autonomous objective modification.
- Candidate edits to evaluators, protected tasks, promotion thresholds, safety policy, historical evidence, or registry history.
- Claiming general Office competence from marker-based local artifacts.
- Expanding the pilot to the planned 90-task main study in this implementation cycle.

## Existing foundation

The implementation extends TaskSpec, SkillManifest, ArtifactRef, EvaluationReport, Orchestrator, MockWorkAgentAdapter, LocalOfficeAdapter, BasicEvaluator, OfficeArtifactEvaluator, ArtifactStore, TraceStore, ToolGateway, path safety, the pilot dataset, and the B0 qualification evidence already present in the repository.

## Target architecture

~~~mermaid
flowchart TB
  BR[Benchmark Runner] --> CE[Champion Execution]
  REG[Skill Registry Champion] --> CE
  CE --> TM[Trace Memory]
  CE --> AS[Artifact Store]
  TM --> FD[Failure Diagnoser]
  AS --> FD
  FD --> CP[Codex Candidate Provider]
  REG --> CP
  CP --> CW[Isolated Candidate Workspace]
  CW --> LC[Leakage Critic]
  LC --> VF[Verifier]
  VF -->|pass| FE[Frozen Evaluator]
  VF -->|reject| RA[Rejected Archive]
  FE --> PC[Promotion Controller]
  PC -->|accept| REG
  PC -->|reject| RA
  PC -->|human review| HG[Human Gate]
  REG --> RB[Rollback Manager]
  FE --> ER[E01-E12 Reports]
~~~

Candidate generation, verification, evaluation, and promotion are separate authorities. Candidate-controlled files have no write access to evaluation, governance, or protected-data paths.

## Core records

CandidatePatch records candidate_id, parent_version, provider and model identity, diagnosis hashes, atomic edits, new tests, edit budget, timestamp, and structured patch content. Every edit names one editable component, one causal hypothesis, and one expected metric.

FailureDiagnosis records run IDs, the observed failure class, evidence hashes, causal hypothesis, recommended editable component, and confidence. The deterministic failure class cannot be overridden by provider narrative.

VerificationReport records pass/fail, critical violations, warnings, executed checks, test and artifact results, and evidence hashes. Missing mandatory checks are critical failures.

SkillVersion records immutable skill and manifest hashes, parent version, candidate origin, status, evidence hashes, and timestamp. Deployment changes only a champion alias.

PromotionDecision records accept, reject, or human_review together with every gate result, score and cost deltas, and evidence hashes.

ExperimentContract freezes dataset and split hashes, evaluator hash and configuration, provider policy, seed, repeat count, time and resource budgets, promotion thresholds, Git commit, and environment inventory.

## Codex candidate provider

The provider invokes installed codex-cli 0.144.2 as a fresh ephemeral process using workspace-write sandboxing, JSONL output, and a JSON output schema. The command working directory is an isolated candidate workspace, never the main repository.

The workspace contains only the champion skill package, selected public diagnosis evidence, candidate-facing interfaces and policies, allowed tests, editable files, and a local AGENTS.md that prohibits protected-data access and direct deployment.

It excludes hidden and protected task files, evaluator source and configuration, promotion thresholds, historical protected evidence, registry history beyond required parent metadata, credentials copied by the project, and unrelated repository files.

The provider record stores command, CLI version, prompt hash, JSONL output, final structured response, duration, exit code, and produced hashes. Timeout, invalid JSON, schema mismatch, or missing patch is a provider failure.

## Candidate workspace

Each candidate receives a new experiment-scoped directory initialized as a standalone Git repository. The exporter accepts only configured relative files, refuses symlinks, path traversal, absolute paths, Windows device names, protected filenames, and oversized files. Only the schema-valid CandidatePatch and allowlisted diff are imported. Candidate directories are retained for evidence and never reused.

## Failure diagnosis

The deterministic diagnoser classifies observable evidence as input, planning, tool, format, semantic, visual, evaluator, or safety failure. It groups repeated failures by task family and component owner. Codex narrative diagnosis may be attached only after labels and evidence references are sealed.

## Leakage critic

Before candidate execution the critic checks protected task IDs and markers, normalized answer fragments, protected hashes and paths, attempts to change evaluator or governance files, task-specific specialization, encoded protected values where detectable, and newly introduced network, subprocess, or filesystem access outside policy. A positive finding is a critical rejection. Candidate-facing reports do not reveal the protected value.

## Verifier

Verification order is fixed:

1. CandidatePatch schema and parent identity.
2. Allowed component and path policy.
3. Leakage critic.
4. Python compilation and imports.
5. Candidate-authored tests under the single top-level tests directory.
6. Repository regression tests relevant to changed components.
7. Sandboxed smoke execution.
8. Office package reopening for Office-generation changes.
9. Resource and timeout limits.
10. Reproducibility replay when required.

The verifier may read a frozen evaluator package but never exposes it to the candidate.

## Frozen evaluator and protected splits

The evaluator runs evolve for diagnosis, develop for paired comparison, regression after develop qualification, and hidden plus OOD only after preceding gates pass. Hidden task content and per-task results remain evaluator-only. Generator-facing outputs receive no hidden details. Governance receives only sealed aggregate results required for a decision.

Evaluator version changes require a new contract. Scores from different evaluator hashes are not compared directly.

## Skill registry and rollback

The registry stores content-addressed immutable packages and a SQLite index. It supports baseline registration, accepted and rejected versions, parent lineage, a mutable champion alias, and evidence references. Rollback moves the alias to an earlier accepted version and never deletes versions, rewrites evidence, or changes historical run references.

## Promotion controller

Promotion requires all applicable gates:

- verification passed with no critical violation;
- develop improvement satisfies the frozen rule;
- no previously passing critical regression task fails;
- aggregate regression stays within tolerance;
- hidden and OOD degradation stays within limit;
- zero-tolerance unsafe actions remain zero;
- cost increase is permitted or justified by measured gain;
- required repeats reproduce;
- high-risk changes receive explicit human approval.

Safety, leakage, regression, reproducibility, and missing-evidence gates are non-compensatory.

## Experiment runner and statuses

The runner consumes the E01-E12 matrix and creates one immutable invocation root per run. It stores contract, arm configuration, data hashes, provider records, candidates, verification reports, evaluation reports, promotion decisions, timing and cost data, command logs, and final status.

Allowed statuses are completed, failed, unavailable, pending_human_audit, and blocked. Completed means every required pilot artifact exists. Existing completed invocation roots are never overwritten.

## E01-E12 pilot interpretation

- E01 runs the fixed champion baseline.
- E02 runs a bounded Self-Refine arm with the matched provider budget.
- E03 compares generator-only and generator-plus-verifier.
- E04 compares monolithic feedback and modular frozen-evaluator feedback without allowing evaluator edits.
- E05 runs the complete promotion loop over permitted pilot splits.
- E06 ablates the verifier and preserves every other contract field.
- E07 creates artifact-evaluator, response-judge, and human-audit records. Without independent human labels the status is pending_human_audit.
- E08 compares a shared data-processing candidate with domain-specific candidates on OOD and cross-domain tasks.
- E09 removes proposal regularization only.
- E10 removes selection regularization only.
- E11 removes the leakage critic only and uses adversarial candidate fixtures plus hidden aggregate evaluation.
- E12 runs the full loop for Word and PowerPoint under the same protected policy.

All results are labeled pilot evidence.

## E07 human audit protocol

The system generates an anonymous audit bundle containing artifact IDs, audit-visible instructions, artifact evidence, and a fixed rubric. It excludes method identity. A human supplies versioned labels in a schema-valid CSV or JSON file. Until that file exists, E07 remains pending_human_audit.

## Error handling and observability

Every operation records command, working directory, timestamps, duration, exit code, stdout and stderr references, Git commit and dirty state, relevant dependency versions, task and split hashes, prompt and patch hashes, provider identity when reported, and failure class.

Provider retries are bounded by the contract. Invalid candidate output is retained and rejected. Workspace escape terminates verification. Office failures are distinct from evaluator failures. Hidden failures expose no hidden details. Registry and promotion writes are transactional. Resume requires matching contract, dataset, evaluator, provider policy, and champion hashes.

## Testing strategy

All tests remain directly under the single top-level tests directory and follow RED-GREEN-REFACTOR. Coverage includes record schemas, candidate workspace allowlists and path safety, provider command construction and failure modes, deterministic diagnosis, leakage fixtures, verifier ordering, contract identity and split isolation, registry immutability and rollback, promotion gates, experiment statuses and resume identity, an end-to-end fake-provider loop, one real Codex provider smoke invocation, and B0 mock and Office non-regression.

Unit tests use a controlled fake provider process. Real Codex integration is a separate evidence run. An unavailable CLI or authentication state cannot be converted into experiment success.

## Security invariants

1. Candidates cannot write the main repository.
2. Candidates cannot read hidden tasks or evaluator and governance internals.
3. Candidates cannot change allowlists, thresholds, or historical evidence.
4. Provider workspaces contain no credentials copied by the project.
5. Imported patches are relative, allowlisted, bounded, and hash-recorded.
6. Hidden results are aggregate-only outside evaluation and governance.
7. Safety, leakage, regression, and reproducibility gates are non-compensatory.

## Deliverables

- executable closed-loop modules under src/workagent_rsi;
- top-level tests for every new component;
- Codex provider schemas and prompts;
- immutable registry and rollback evidence;
- E01-E12 experiment contracts and runner;
- honest pilot status roots for every attempted experiment;
- an E07 anonymous audit bundle;
- updated Agent.md, README, execution plan, and artifact manifest;
- docs/project_overview_zh.md covering research basis, architecture, components, data, pipeline, experiments, evidence, limitations, and reproduction.

## Acceptance criteria

1. The full automated suite passes using Python 3.12.
2. All tests remain in the single top-level tests directory.
3. A fake-provider candidate can be diagnosed, generated, verified, evaluated, registered, promoted, and rolled back end to end.
4. A real ephemeral Codex smoke invocation produces a schema-valid candidate or an evidence-backed failed or unavailable record.
5. Access tests prove hidden, evaluator, and governance files are absent from candidate workspaces.
6. B0 mock and local Office qualification remain non-regressed.
7. Every E01-E12 experiment has a real immutable status record and no fabricated score.
8. E07 remains pending_human_audit until independent human labels are supplied.
9. Registry versions and historical evidence remain immutable and rollback only moves the champion alias.
10. The Chinese overview distinguishes implemented results, pilot evidence, pending human evidence, and unperformed main-study work.

