# Task 5 report — YAML CLI and package resources

## Status

Implemented the WorkAgent CLI provider option, task-YAML-relative Office inputs via `Harness(input_base=...)`, package resource inclusion, and README guidance. The YAML task shape is unchanged.

## RED / GREEN evidence

- RED: `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t5 tests/test_workagent_office.py -k cli` produced **2 failed, 1 passed**. The explicit provider test failed because argparse rejected `workagent`; the relative-input test failed because staging searched the shell directory and returned `FAILED` instead of `UNAVAILABLE`. The default Office-provider test already passed.
- GREEN: the same focused command produced **3 passed, 56 deselected** after the CLI change.
- Full module: `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t5-full tests/test_workagent_office.py` produced **56 passed, 3 skipped**.
- `py -3.12 -m compileall -q src/workagent_rsi` and `git diff --check` exited successfully. The latter emitted line-ending warnings for existing dirty files and changed files, but no whitespace errors.
- Package import and `importlib.resources` lookup for both files succeeded. A wheel built with `py -3.12 -m pip wheel --no-deps --no-build-isolation -w project_artifacts/results/test-runs/plan-t5-wheel .`; ZIP inspection confirmed `workagent_rsi/prompts/office_agent.md` and `workagent_rsi/schemas/agent_response.schema.json` are included.

## Files

- `src/workagent_rsi/cli.py`: accept `workagent`; pass the resolved YAML parent as `input_base` so relative inputs are resolved there by the existing validated staging path.
- `pyproject.toml`: include prompt Markdown and schema JSON as setuptools package data.
- `tests/test_workagent_office.py`: cover explicit provider, default Office provider, and YAML-relative input staging from another working directory.
- `README.md`: add an Office edit example, supported suffixes, default local model, no-template-fallback behavior, and read-isolation limit.

## Concerns / limits

- No real model was launched and no sensitive inputs were used. The tests simulate an unavailable Codex executable at the subprocess boundary.
- Codex `workspace-write` has not been verified to prevent reads outside the task workspace. Do not use sensitive inputs until that property is established.
- Source `input_files` stay relative in the YAML payload; the CLI supplies the resolved YAML parent to `Harness`, and the established input-staging code resolves and validates paths against that base. This retains traversal and symlink checks.
- Existing dirty design/spec, execution log, and plan files were not changed or staged as part of this task.

## Review fix round 1

- Verified the binding issue: `Harness._paths` uses an explicit output's parent as the run root, so an unrestricted CLI path could relocate all run evidence.
- RED: after adding CLI path-boundary tests, `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t5-review-red tests/test_workagent_office.py -k cli` produced **5 failed, 4 passed**. Outside/traversal results directories and outside/traversal/root-level output files were accepted instead of rejected. The allowed in-results output case passed.
- GREEN: the focused command using `--basetemp=project_artifacts/results/test-runs/plan-t5-review-green2` produced **9 passed, 56 deselected**. The full module using `--basetemp=project_artifacts/results/test-runs/plan-t5-review-full` produced **62 passed, 3 skipped**. Compilation and `git diff --check` succeeded; only line-ending warnings were emitted.
- `cli.py` now resolves the working project's `project_artifacts/results` root and both custom paths before checking containment. Custom `--results-dir` must remain under that root. Explicit `--output` must be under the selected results directory and have a per-run child directory between that directory and the output file. Invalid paths are rejected before the YAML is run. Using the working project keeps the CLI usable when installed as a wheel rather than tying output to the package installation directory.
- `README.md` now keeps the example pytest base temp under `project_artifacts/results/test-runs/` and disables pytest's cache provider.
- The first RED run created a smoke-test directory outside `results` before rejection existed. After verifying its exact source and destination, it was moved into `project_artifacts/results/test-runs/plan-t5-review-red/escaped-results`. No real model or sensitive data was used.
- Final verification after the working-project path refinement: `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t5-review-final tests/test_workagent_office.py` produced **62 passed, 3 skipped**; compilation and `git diff --check` succeeded.
