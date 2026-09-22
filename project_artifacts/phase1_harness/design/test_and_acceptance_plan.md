# Test and Acceptance Plan

## Test layout

All automated tests live in one top-level `tests/` directory. Files are named by responsibility, for example `tests/test_contracts.py`, `tests/test_orchestrator.py`, `tests/test_evaluator.py` and `tests/test_pipeline_e2e.py`. No phase-specific test trees are created under `project_artifacts/`.

## Test layers

1. **Unit**: schema validation, state transitions, hash generation, tool allowlist, evaluator gates.
2. **Integration**: mock WorkAgent + sandbox + artifact store + SQLite trace memory.
3. **End-to-end**: one smoke success, one complete task and one controlled failure.
4. **Office adapter**: gated tests that skip with an explicit environment reason when LibreOffice or fixture files are unavailable.

## Acceptance metrics for Phase 1A

- Every component has a documented responsibility and interface.
- State machine includes normal, retry, failure and resume paths.
- Candidate-controlled code cannot modify evaluator/hidden-test inputs.
- Test commands and expected evidence are specified.
- No document claims a pipeline run that has not occurred.

## Phase 1B verification commands

```powershell
py -3.12 -m pytest -q
py -3.12 -m workagent_rsi.cli run examples/smoke_task.yaml --config configs/local.yaml
py -3.12 -m workagent_rsi.cli inspect-run <run_id>
```

The exact CLI paths may be adjusted during implementation, but every executed command, exit code, stdout/stderr and generated artifact must be copied into the run report.

