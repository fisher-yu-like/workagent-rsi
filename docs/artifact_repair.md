# Task repair

`Harness.run(task, repair_policy=RepairPolicy(max_repairs=2))` opts into task-local repair. Import `RepairPolicy` from `workagent_rsi.repair_loop`. Without this option, behavior is unchanged. `max_attempts` continues to mean execution retry.

A repair starts only after a confirmed agent execution failure or a complete assessment that rejects an artifact. Missing environment capability, unknown failure origins and incomplete specifications or assessment channels stop repair. Each attempt uses the same frozen task, skill and evaluator and gets a separate execution workspace, content-addressed artifact store and assessment reports. Every mandatory check, including source preservation checks present in the frozen spec, runs again.

The execution view receives the original task instruction, staged input hashes, the most recently executed source snapshot (with exact hash), authorized develop issues and trace-grounded diagnoses. Current code is capped at 100,000 bytes in total. It receives copies of earlier artifacts, never evaluator report directories. The task-level skill registry is not changed by this loop.

`repair-loop/attempt-manifest.json`, per-attempt requests/results/code manifests and `before-after-reports.json` retain the history. `Harness.resume` returns the selected persisted state and trace; it does not rerun an interrupted task.

T21 qualification uses real openpyxl and python-docx artifacts with authored provider substitutes. It is not a live model repair or RSI improvement result. T22 adds the rules below.


## Budget and feedback boundaries

Pass the same `RunBudget(max_model_calls=24, max_tool_calls=64, max_repairs=2, max_wall_seconds=600)` instance to `Harness.run(..., run_budget=budget)`, `WorkAgentFrozenEvaluator(..., run_budget=budget)` or `WorkAgentExperimentRunner(..., run_budget=budget)`. A repair policy without an explicit budget creates a default bounded budget; an experiment or frozen evaluator shares it across tasks and repeats. A budget is a runtime counter and grants no live-call approval. Actual live configuration still follows the T03 approval contract.

Native execution API requests, HTTP retries, tool attempts, semantic/visual judge retries and the API candidate generator reserve before launch and reconcile afterward. Failed and interrupted calls stay charged. The ledger retains reservation and reconciliation times. Optional monetary caps require a known conservative cost upper bound; current provider adapters do not supply pricing bounds, so such calls are refused when `max_cost_usd` is set. Unknown actual cost is not reported as zero.

The execution and candidate Codex CLI providers own opaque model/tool loops. When a shared runtime budget is active they return unavailable before launch. Use the metered native API backend for a bounded execution loop. The read-only judge CLI has tools disabled and charges each explicit invocation. These are local boundary tests; the metered native backend has not received new live qualification in T21/T22.

Deadlines include initial execution, full assessment and repairs. Transport/subprocess/tool timeouts are clamped to the remaining budget; a native tool needs at least one full second remaining. The counter checks elapsed time again after a call and refuses a late result or subsequent call. Blocking third-party transports and operating-system cleanup can exceed a requested timeout; arbitrary injected Python callbacks cannot be forcibly terminated by this in-process counter. Such cases remain incomplete rather than accepted within budget.

Only `split_name="develop"` with `hidden_test=False` permits assessment-driven repair. Regression, hidden, promotion validation, protected, OOD and final-test runs retain their first assessment and never create a repair request. Executors may still perform the same fixed public self-checks on all splits. A visibility/contract violation invalidates the cohort and returns an incomplete outcome.

`allowed_artifacts` contains keys from the frozen acceptance spec. Empty means all declared outputs. Changes to an output outside that set reject the attempt, even if its quality checks pass. The loop stops after a pass, the repair cap, a deadline, repeated artifact/code state or two attempts without a better rank. Selection prefers accepted, fully assessed results, then fewer critical failures and higher score; ties keep the earlier result. All rejected attempts remain in history.

`repair-loop/best-result.json` is updated atomically before the next repair. A failed repair cannot replace an earlier assessed file. If repair later encounters an environment/transport/assessment gap, the earlier file remains available while the overall outcome is incomplete. Interruptions preserve the best result, completed attempts, pending request, interruption record and budget ledger. Resume reads evidence; active recovery is reserved for T30.

Experiment identity binds the repair policy and budget limits, so runs with different caps cannot silently share the same frozen evaluator identity. Formal matching of comparison arms and final live qualification remain T31/T32 work.
