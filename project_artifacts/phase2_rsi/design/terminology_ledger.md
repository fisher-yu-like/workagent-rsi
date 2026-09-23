# Terminology Ledger

| Canonical term | Definition | Decision |
|---|---|---|
| WorkAgent-RSI | Benchmark-Driven Recursive Skill Improvement for Office Agents | Project name |
| Recursive Skill Improvement (RSI) | Persistent, evidence-backed improvement of versioned skills and harness behavior | Never expand as unrestricted self-modification |
| champion | Currently registered skill version used as comparison baseline | Lowercase in prose/code identifiers |
| candidate | Proposed successor skill version that has not passed promotion | Never call deployed |
| evolve split | Tasks visible to candidate generation and iterative search | Separate from hidden/OOD |
| protected regression set | Previously solved tasks that candidates must preserve | Evaluator-owned and read-only |
| hidden test set | Tasks unavailable to candidate generation | Release only aggregated results |
| out-of-distribution (OOD) | Tasks/templates/domains outside the evolve distribution | Define once, then OOD |
| critical gate | Non-compensatory safety or correctness condition | Failure rejects candidate regardless of score |
| noise band delta | Empirical score variation of repeated unchanged champion runs | Written as `delta` in text and config |
| cost per validated gain | Total run cost divided by accepted score improvement | Report tokens, time and tool calls separately |
