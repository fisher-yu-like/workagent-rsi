# WorkAgent-RSI Training and Evaluation Plan

## Goal

Test whether modular, independently verified skill improvement increases Office task success and artifact quality without increasing unsafe actions, regressions or cost beyond configured limits. Phase 2 defines the protocol only; no training or benchmark score has been produced.

## Hypotheses and experiments

| Hypothesis | Test | Primary metric | Required comparison |
|---|---|---|---|
| H1 Modular gen/verify/evaluator is more controllable than monolithic reflection | E01-E05 | task success, diagnosis accuracy, invalid promotion rate | Fixed, Self-Refine, gen-only, gen+verify, full RSI |
| H2 Independent verification reduces regressions | E03-E06 | critical regression rate | with vs without verifier |
| H3 Artifact-level evaluation better captures success | E07 | disagreement and agreement with an independently configured response-only judge | response judge vs file evaluator |
| H4 Some Excel skills transfer to Word/PPT | E08 | cross-domain transfer delta | domain-specific vs shared component |
| H5 Protected splits and regularization reduce overfitting | E09-E11 | hidden/OOD delta, evolve-hidden gap | unregularized vs RRSI |

## Baselines

- B0 Fixed skill, no RSI.
- B1 Monolithic Self-Refine with the same execution budget.
- B2 Generator only; best develop score wins.
- B3 Generator plus verifier.
- B4 Generator, verifier and frozen evaluator.
- B5 Full WorkAgent-RSI with RRSI edit budget, leakage critic, protected splits, cost gate and rollback.

All methods receive the same task access, model/executor, candidate count and total token/tool budget. Any unavailable provider-specific feature is disabled for every arm.

## Data requirements and splits

### Pilot

Create 30 auditable tasks: 10 Excel, 10 Word and 10 PowerPoint, balanced across easy/medium/hard. The pilot validates tooling and estimates variance; it is not powered for a final claim.

### Main study target

Expand to at least 90 independently sourced or generated tasks, 30 per domain. Split by source/template family before deduplication-aware assignment:

- evolve: 40%
- develop: 20%
- protected regression: 15%
- hidden test: 15%
- OOD/transfer: 10%

Adversarial variants are linked to parent tasks and evaluated separately, not mixed into ordinary averages. Final counts may change after license and leakage audit; every change must be versioned before experiments begin.

## Task and artifact metrics

### Primary

- critical-gate task success rate;
- artifact correctness score;
- protected regression rate;
- hidden/OOD score delta from champion;
- unsafe action rate.

### Secondary

- structural and visual quality;
- iterations to validated gain;
- tool calls, policy tokens, wall time and monetary cost;
- cost per validated gain;
- skill activation and faithful-use rate;
- cross-domain transfer delta.

Report per-task distributions, bootstrap 95% confidence intervals and paired comparisons where tasks are shared. Do not report only macro averages.

## Default RRSI configuration

| Parameter | Pilot default | Rationale |
|---|---:|---|
| rounds | 6 | Enough to observe trajectory without unlimited adaptive access |
| candidates per round | 4 | Bounded search cost |
| `b_max` atomic edits | 4 | Early coordinated exploration |
| `b_min` atomic edits | 1 | Late attribution |
| noise calibration repeats | 3 | Initial variance estimate; increase if unstable |
| stall window | 2 rounds | Trigger structured exploration quickly in pilot |
| pruning window | 3 rounds | Remove persistent non-contributors |
| seeds | 3 | Pilot reproducibility; main study should use 5 where budget permits |
| max task timeout | 300 s | Prevent runaway Office operations |
| critical regression tolerance | 0 | Previously passing critical task may not fail |
| aggregate regression tolerance | 1 percentage point | Initial value; freeze before hidden evaluation |
| hidden/OOD degradation limit | 1 percentage point | Conservative pilot gate |

Thresholds are planning defaults. Phase 3 must calibrate them from unchanged-champion repeats before candidate evaluation and freeze them before accessing hidden results.

## Optimization stages

1. **Environment qualification**: validate Office engines, fonts, locale, recalculation and render parity.
2. **Baseline**: execute B0 across all non-hidden splits and repeat for noise calibration.
3. **Failure taxonomy**: label input, planning, tool, format, semantic, visual, evaluator and safety failures.
4. **Candidate generation**: create atomic edits within the annealed budget and attach new tests.
5. **Verification**: schema, leakage, permissions, sandbox, Office structure and protected regression checks.
6. **Develop evaluation**: paired task evaluation under the same budget.
7. **Protected evaluation**: regression, then hidden/OOD, with aggregate-only feedback to the generator.
8. **Promotion or rejection**: record every gate and evidence reference.
9. **Replay**: reproduce accepted candidates from clean environments and required seeds.
10. **Transfer**: freeze the skill and run unseen templates/domains/executors.

## Ablations

- Remove proposal regularization.
- Remove selection regularization.
- Remove leakage critic.
- Remove protected regression set.
- Remove cost-aware acceptance.
- Replace artifact-level evaluator with response-only judge.
- Disable negative-evidence history.
- Disable pruning.

## Repetition and statistics

- Pilot: three seeds or repeated deterministic runs where the executor is stochastic.
- Main study: five seeds when feasible; otherwise justify reduced repeats using observed variance.
- Use paired bootstrap intervals for success/score deltas and McNemar tests for paired binary task outcomes where assumptions hold.
- Correct multiple primary comparisons or pre-register one primary contrast: B5 versus B1.
- Treat missing/failed runs as failures unless a predeclared infrastructure exclusion applies.

## Checkpoints and recovery

Checkpoint after every candidate verification and split evaluation. A checkpoint contains task/split manifest hashes, skill/evaluator versions, environment image or inventory, random seed, run IDs, evidence hashes and remaining budget. Resume never reuses partial artifacts as successful output.

## Hardware and execution strategy

The current host has 16 CPU cores, 16 GB RAM and an 8 GB RTX 5060 Laptop GPU. This is sufficient for orchestration, Office processing, rendering and small local models, but not for full training of large foundation models. The default plan uses remote frozen policies and local deterministic evaluators. Optional local experiments are limited to quantized small models or lightweight adapters after a separate feasibility gate.

## Estimated time and budget

Planning estimates use run units rather than current vendor prices. One run unit is one task execution plus evaluation. Pilot B0-B5 over 30 tasks and three repeats requires approximately 540 baseline run units before candidate-search overhead. A six-round full RSI search with four candidates is therefore restricted to Excel first and capped by the resource sheet. Phase 3 must fill vendor prices and measured median run time before authorizing the main study.

## Go or No-Go criteria

Proceed from pilot to main study only if:

- at least 95% of task fixtures execute deterministically enough for scoring;
- evaluator-human agreement reaches the predeclared target on an audit sample;
- no candidate can write protected evaluator/test data;
- accepted candidates reproduce across required repeats;
- B5 does not increase unsafe actions or critical regressions;
- projected main-study cost fits the approved budget.

Stop or redesign if hidden/OOD performance repeatedly regresses, evaluator disagreement remains high, Office render environments are unstable, or validated gain per unit cost does not exceed B1.

## Known risks

- Provider and Office-engine differences may dominate skill effects.
- Thirty pilot tasks are too small for strong generalization claims.
- Visual judges may be sensitive to font/rendering differences.
- Candidate generation can indirectly infer develop-task details through repeated feedback.
- Skill-library growth can reduce retrieval quality even when each skill passed admission tests.
