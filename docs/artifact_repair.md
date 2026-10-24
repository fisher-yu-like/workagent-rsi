# Task repair

`Harness.run(task, repair_policy=RepairPolicy(max_repairs=2))` opts into task-local repair. Import `RepairPolicy` from `workagent_rsi.repair_loop`. Without this option, behavior is unchanged. `max_attempts` continues to mean execution retry.

A repair starts only after a confirmed agent execution failure or a complete assessment that rejects an artifact. Missing environment capability, unknown failure origins and incomplete specifications or assessment channels stop repair. Each attempt uses the same frozen task, skill and evaluator and gets a separate execution workspace, content-addressed artifact store and assessment reports. Every mandatory check, including source preservation checks present in the frozen spec, runs again.

The execution view receives the original task instruction, staged input hashes, bounded current source, authorized develop issues and trace-grounded diagnoses. It receives copies of earlier artifacts, never evaluator report directories. The task-level skill registry is not changed by this loop.

`repair-loop/attempt-manifest.json`, per-attempt requests/results/code manifests and `before-after-reports.json` retain the history. `Harness.resume` returns the selected persisted state and trace; it does not rerun an interrupted task.

T21 qualification uses real openpyxl and python-docx artifacts with authored provider substitutes. It is not a live model repair or RSI improvement result. Budget, protected split and best-result rules are delivered by T22.
