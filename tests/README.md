# Tests

All automated tests for WorkAgent-RSI live directly in this single top-level directory. The suite covers contracts, storage, orchestration, Office adapters/evaluators, path safety, candidate isolation/provider execution, deterministic diagnosis, leakage verification, frozen evaluation, immutable registry, promotion/rollback and E01-E12 orchestration. No phase-specific test subdirectories are used.

## Current hardening handoff

Continue development in `D:/ws/Projects/WorkAgent-RSI-hardening` on
`feat/evaluation-rsi-hardening`. The original `WorkAgent-RSI` checkout remains
on its older feature branch with the user's notes preserved. The shared task
ledger is `project_artifacts/formal_study/hardening_task_ledger.json`, and the
canonical plan is `docs/superpowers/plans/2026-10-16-evaluation-rsi-hardening.md`.

T01 adds twelve **active, expected-open** regressions. A normal full pytest run
must include them and currently fails. Their manifest records independent
truth sources, minimal inputs and the responsible repair tasks. A captured red
baseline completes T01's evidence-delivery task; it does not fix those defects.
No xfail, skip, default exclusion or score-threshold change hides them.

From the hardening worktree, with an explicit Python 3.11+ interpreter:

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
