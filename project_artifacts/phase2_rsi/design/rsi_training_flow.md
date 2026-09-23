# RSI Training and Optimization Flow

The initial optimization target is a skill/harness package. “Training” includes prompt search, tool-policy search, Office script repair and verifier/test generation. Model-weight updates are a later optional track.

```mermaid
stateDiagram-v2
  [*] --> BASELINE
  BASELINE --> NOISE_CALIBRATION
  NOISE_CALIBRATION --> DIAGNOSE
  DIAGNOSE --> PROPOSE
  PROPOSE --> VERIFY
  VERIFY --> REJECTED: critical failure
  VERIFY --> DEVELOP_EVAL: pass
  DEVELOP_EVAL --> REGRESSION_EVAL: gain exceeds rule
  DEVELOP_EVAL --> REJECTED: insufficient evidence
  REGRESSION_EVAL --> HIDDEN_OOD_EVAL: no critical regression
  REGRESSION_EVAL --> REJECTED: regression
  HIDDEN_OOD_EVAL --> HUMAN_GATE: high risk
  HIDDEN_OOD_EVAL --> PROMOTED: low or medium risk and gates pass
  HUMAN_GATE --> PROMOTED: approved
  HUMAN_GATE --> REJECTED: rejected
  PROMOTED --> DIAGNOSE: next round
  REJECTED --> DIAGNOSE: budget remains
  DIAGNOSE --> [*]: stop rule
```

## Optimization stages

### Stage A Pilot

Use 30 tasks, ten per Office domain, to validate schemas and graders. Run fixed prompt and single-pass self-refine baselines. No research claim depends on pilot significance.

### Stage B Excel closed loop

Prioritize deterministic cell, formula, formatting and chart assertions. Compare fixed skill, self-refine, generator-only, generator+verifier and full RSI under matched candidate budgets.

### Stage C Word and PowerPoint expansion

Add OOXML, render and visual checks. Preserve the same promotion controller while allowing domain-specific evaluators.

### Stage D Transfer and robustness

Freeze evolved skills and test unseen templates, cross-domain components and a second executor/model. Measure activation, faithful use and downstream benefit separately.

## Stop rules

- Candidate budget exhausted.
- Three consecutive rounds produce no gain beyond `delta`.
- Expected validated gain falls below projected cost.
- Unsafe action or critical regression rate crosses zero-tolerance gate.
- Evidence integrity, evaluator independence or environment reproducibility fails.
- Human reviewer stops a high-risk branch.
