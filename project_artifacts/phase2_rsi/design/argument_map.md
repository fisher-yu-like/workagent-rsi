# Phase 2 Argument Map

## Central question

How can an Office agent convert execution failures into persistent skill improvements without overfitting the benchmark, weakening prior capabilities or allowing the candidate to control its own evaluation?

## Thesis

WorkAgent-RSI should implement bounded L1/L2 autonomy through four separated authorities: a candidate generator, an independent verifier, a frozen evaluator and a promotion controller. Every retained change must carry its originating evidence, pass protected splits and justify added resource cost.

## Supporting arguments

1. Office outputs expose machine-checkable structure, enabling stronger verification than response-only agent benchmarks.
2. RRSI-style sparse proposals and conservative selection make multi-round changes more attributable and less benchmark-specific.
3. Immutable evidence and version lineage make rollback and longitudinal analysis possible.
4. A staged Excel-first protocol reduces uncertainty before adding Word and PowerPoint visual evaluation.

## Counterarguments and controls

- A better score may reflect evaluator exploitation. Control: hidden tests, leakage critic, deterministic assertions and frozen evaluator versions.
- Skill accumulation may harm retrieval. Control: applicability conditions, activation metrics, pruning and retirement tests.
- More autonomy may increase cost without improving successors. Control: matched budgets, cost per validated gain and explicit stopping rules.
- Cross-domain transfer may be weak. Control: report null or negative transfer and retain domain-specific skills where necessary.
