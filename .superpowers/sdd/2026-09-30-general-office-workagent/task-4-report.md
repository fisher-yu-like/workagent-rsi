# Task 4 Report: Harness Integration

## RED evidence

Command:

```powershell
py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t4 tests/test_workagent_office.py -k harness
```

Initial result: collection succeeded and the two initial integration tests failed as intended:

```text
TypeError: Harness.__init__() got an unexpected keyword argument 'workagent_config'
ValueError: unknown execution provider: workagent
2 failed, 48 deselected
```

The first run also exposed a test syntax typo, which was corrected before the production implementation; the next run failed only for the missing provider/configuration behavior above.

## GREEN evidence

Focused Harness integration:

```text
py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t4 tests/test_workagent_office.py -k harness
6 passed, 48 deselected in 2.01s
```

Requested Office/Harness regression:

```text
py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t4 tests/test_workagent_office.py tests/test_simple_harness.py tests/test_office_adapter.py tests/test_office_evaluator.py
63 passed, 3 skipped in 3.80s
```

Full top-level suite:

```text
py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t4-full tests
137 passed, 3 skipped in 43.06s
```

`git diff --check` reported no whitespace errors. Git emitted only normal LF-to-CRLF working-copy warnings for touched text files.

## Implemented behavior

- Added `workagent` provider selection, with normal Office tasks defaulting to WorkAgent while smoke tasks retain the smoke adapter.
- Passed `WorkAgentConfig`, agent instructions, and input base through `Harness` and `Run`.
- Added `WorkAgentOfficeAdapter` event flow: `started`, `input_manifest`, `provider_output`, validated `artifact`, and one terminal failure/unavailable event.
- Re-verified source and staged input hashes after every provider exit before accepting artifacts.
- Mapped timeout to a terminal `failure` event with `status="timeout"`; unavailable remains `unavailable`. Neither reaches evaluation success or produces a template artifact.
- Preserved unique Harness result/workspace directories and existing `ArtifactStore` copying/evaluator behavior.
- Updated the legacy normal Office smoke test to select `local_office` explicitly.

## Files changed

- `src/workagent_rsi/workagent_office.py`
- `src/workagent_rsi/orchestrator.py`
- `src/workagent_rsi/run.py`
- `src/workagent_rsi/harness.py`
- `tests/test_workagent_office.py`
- `tests/test_simple_harness.py`

## Concerns

- The real Codex/Ollama process was not run; integration tests inject a deterministic `subprocess.run` provider and create genuine `.xlsx` files with openpyxl.
- Input paths default to the process working directory unless callers provide `input_base`; the YAML CLI path-resolution work is outside Task 4.
- Existing unrelated dirty docs/spec/log changes were preserved and not staged.
