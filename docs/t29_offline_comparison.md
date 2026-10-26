# T29 offline comparison core

The user authorized a small amount of later local work while deferring human review. `workagent_rsi.statistical_promotion` implements only the local paired comparison core. It is not connected to `PromotionController`, the RSI loop, real providers or the evaluator. T29 remains incomplete.

`RepeatedObservation` preserves task, family, domain, repeat, execution identity, execution validity, score qualification, judge observation identity and protocol identity. `compare_repeated_runs` requires matching task/repeat pairs, unchanged source identities, three independent execution identities per task and a matching declared protocol. Missing pairs, invalid executions or reused judge observations leave the comparison inconclusive. A hash supplied to this local function is a declaration; later integration must verify its provenance.

Valid candidate execution failures remain in the denominator and switch the automatic primary metric to task success rate. Artifact quality is used only when executions succeed and all quality observations are comparable. Whole families are resampled for a paired bootstrap; repeats do not become independent families. The policy records the seed,10,000 resamples,0.05 minimum improvement and0.01 protected-domain degradation threshold. The eight-family minimum is an engineering gate, not a statistical power justification.

Critical regressions, unsafe actions and any protected-domain regression reject the comparison. A positive mean with an interval crossing zero stays inconclusive. Even a positive result is named `eligible_statistical_signal`; the returned `research_qualified` field is always false. This core never promotes a version.

The saved example at `project_artifacts/results/hardening-v2/T29-local/20261026/` uses explicitly synthetic observations. It demonstrates local calculations, not actual agent performance or human agreement. Focused tests cover denominators, execution failures, uncertainty, protected domains, repeated cached judgements and the qualification boundary.

Remaining T29 work includes controller integration, actual execution/judge provenance, comparable budget and time-window validation, interleaved baseline/candidate scheduling, execution-versus-judge variance, cross-batch regression gates and actual repeated comparisons under qualified data and evaluators. No model, worker or judge is called by this delivery.
