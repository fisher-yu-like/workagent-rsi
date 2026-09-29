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
