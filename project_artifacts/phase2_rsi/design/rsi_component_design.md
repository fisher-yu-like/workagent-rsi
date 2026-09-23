# RSI Component Design

| Component | Input | Output | Frozen or mutable | Failure handling |
|---|---|---|---|---|
| Experience collector | Task, trace, artifacts, versions | `ExperienceRecord` | Append-only | Mark incomplete records; never infer missing output |
| Failure diagnosis | Failed/low-score records | Ranked intervention hypotheses | Versioned | Require evidence pointers and confidence |
| Candidate generator | Champion, diagnosis, edit history, budget | `CandidatePatch[]` | Mutable strategy, bounded targets | Invalid patches never reach execution |
| Leakage critic | Candidate diff and task metadata policy | pass/fail findings | Frozen per experiment | Reject before scoring |
| Verifier | Candidate, manifest, sandbox, regression fixtures | `VerificationReport` | Frozen per epoch | Critical violation rejects candidate |
| Evaluator | Task split, artifact, trace, evaluator config | `EvaluationReport` | Frozen per experiment | Missing evidence is failure, not zero-filled success |
| Benchmark runner | Split manifest, seed, budget | Comparable run bundle | Config-driven | Resume by immutable run manifest |
| Promotion controller | Champion/candidate reports, policy | `PromotionDecision` | Human-defined policy | Default reject on missing evidence |
| Skill registry | Accepted version package | Immutable `SkillVersion` | Append-only versions | Alias rollback |
| Trace memory | All events and decisions | Query/export API | Append-only | Transaction and checksum checks |
| Artifact store | Inputs/outputs/reports | Content-addressed refs | Append-only | Hash mismatch blocks use |
| Monitoring | Deployed run outcomes | Drift/regression alerts | Versioned rules | Trigger rollback review |

## Core records

```yaml
ExperienceRecord:
  run_id: string
  task_version: string
  split: evolve|develop|regression|hidden|ood|adversarial
  skill_version: string
  evaluator_version: string
  trace_ref: sha256
  artifact_refs: [sha256]
  metrics: object
  failure_labels: [string]
  cost: {tokens: int, tool_calls: int, seconds: float}

CandidatePatch:
  candidate_id: string
  parent_version: string
  atomic_edits: [{component: string, hypothesis: string, diff_ref: sha256}]
  expected_metrics: [string]
  edit_budget: int
  new_tests: [string]

PromotionDecision:
  candidate_id: string
  decision: accept|reject|human_review
  gates: object
  score_delta: float
  noise_band: float
  regression_delta: float
  ood_delta: float
  cost_delta: float
  evidence_refs: [sha256]
```

## Editable component policy

Initially editable: skill prompt, tool selection policy, context assembly, Office operation script, deterministic verifier rules and candidate-authored regression tests. Protected: benchmark labels, hidden tasks, evaluator weights/prompts, promotion thresholds, tool allowlist, evidence store and registry history. Changes to protected improvement mechanisms require a separate L5 protocol and independent anchor evaluation.
