# Tests

All automated tests for WorkAgent-RSI live directly in this single top-level directory. The suite covers contracts, storage, orchestration, Office adapters/evaluators, path safety, candidate isolation/provider execution, deterministic diagnosis, leakage verification, frozen evaluation, immutable registry, promotion/rollback and E01-E12 orchestration. No phase-specific test subdirectories are used.

## Current hardening handoff

Continue development in `D:/ws/Projects/WorkAgent-RSI` on the existing
`feat/evaluation-rsi-hardening` branch. The sibling checkout is historical.
The shared task
ledger is `project_artifacts/formal_study/hardening_task_ledger.json`, and the
canonical plan is `docs/superpowers/plans/2026-10-16-evaluation-rsi-hardening.md`.

T01 added twelve active regressions. A normal full pytest run must include all
of them. R12 now passes through fail-closed execution; R01?R11 remain open. Their manifest records independent
truth sources, minimal inputs and the responsible repair tasks. A captured red
baseline completes T01's evidence-delivery task; it does not fix those defects.
No xfail, skip, default exclusion or score-threshold change hides them.

From the current repository directory, with an explicit Python 3.11+ interpreter:

```powershell
$TaskPython = 'D:/ws/Projects/WorkAgent-RSI/.venv/Scripts/python.exe'
& $TaskPython project_artifacts/phase3_experiments/scripts/run_hardening_checks.py T01 tests/test_review_regressions.py tests/test_candidate_boundary_regressions.py tests/test_review_case_manifest.py
& $TaskPython project_artifacts/phase3_experiments/scripts/run_hardening_checks.py T03 tests/test_run_contracts.py tests/test_evidence_bundle.py
& $TaskPython project_artifacts/phase3_experiments/scripts/run_hardening_checks.py handoff-full
```

Each invocation creates an exclusive evidence directory with the command,
commit, source hashes, environment, timestamps, stdout/stderr, exit code,
JUnit cases and a ZIP archive of generated files. Short temporary paths avoid
Windows long-path failures. Exit codes are preserved, including T01's red result.
The R12 probe executes only authored test code, reads only its own dummy parent
file, and supplies a sanitized child environment with an artificial sentinel.
It is not real model or sandbox qualification.

T03 provides additive `ExecutionOutcome`, `AssessmentOutcome`, `RunUsage` and
`ProtocolCapabilities` types plus explicit adapters for old reports. Missing
telemetry remains null/unavailable; observed zero requires an available status.
Legacy ambiguous failure origins remain null. Executor transport availability
does not imply judge, Responses, image or structured-output availability.
`write_evidence_bundle` creates portable, checksummed file references and rejects
credential metadata; callers must sanitize arbitrary file bodies themselves.
These contracts do not yet change pipeline behavior or repair the T01 cases.

## T03 policy and T04 execution boundary

`test_live_call_policy.py` checks explicit approval, hard caps, identity and
credential-free metadata. The approval contract does not implement T22/T31
runtime budget reservations. `test_execution_sandbox.py` checks the actual
Docker command, image identity, bounded output, source/export integrity, owned
cleanup and native provider routing. `test_apptainer_sandbox.py` checks task-only
SSH data, strict runtime policy, exports and fail-closed cleanup using stubs.
Unit tests do not connect to SSH or a model.

Real authored probes require an explicit command:

```powershell
& $TaskPython project_artifacts/phase3_experiments/scripts/probe_execution_sandbox.py --policy <sandbox-policy.json> --execute
```

The command writes exclusive raw boundary/runtime/timeout evidence and actual
XLSX/DOCX/PPTX artifacts. See `deploy/agent-runtime/README.md` and
`project_artifacts/formal_study/hardening_t04_execution_boundary.json` for the
qualified backend, source identities and remaining limits. T05's authorized
input export and Office worker boundaries are still pending.
