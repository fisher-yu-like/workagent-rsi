# Simple Harness Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give users a small, understandable `Harness` API, make one normal run succeed using the task's requested content, and place all new run evidence under one results directory.

**Architecture:** Keep the existing security and evaluation classes internally, while adding short public modules named `data`, `run`, `learn`, `check`, `store`, and `harness`. `Harness.run()` creates one run directory containing the task, result, trace, artifacts and any skill data. Existing long module paths remain as compatibility imports for the current suite and experiment evidence.

**Tech Stack:** Python 3.11+, Pydantic, PyYAML, openpyxl, python-docx, python-pptx, SQLite, pytest.

**Spec:** User-approved chat design: one public `Harness` entry point with short internal names; normal single-round pipeline; no default deliberately broken baseline; one unified results folder.

## Global Constraints

- Keep all tests in the single top-level `tests/` directory.
- Preserve candidate, verifier, evaluator and promotion trust boundaries.
- Do not modify or delete historical evidence.
- Generated Office files must remain genuine XLSX, DOCX or PPTX files.
- The default results directory is `project_artifacts/results`.
- Existing compatibility imports and E01-E12 historical replay paths remain usable.

### Task 1: Public short-name API

**Files:**
- Create: `src/workagent_rsi/data.py`
- Create: `src/workagent_rsi/run.py`
- Create: `src/workagent_rsi/learn.py`
- Create: `src/workagent_rsi/check.py`
- Create: `src/workagent_rsi/store.py`
- Create: `src/workagent_rsi/harness.py`
- Modify: `src/workagent_rsi/__init__.py`
- Test: `tests/test_simple_harness.py`

**Interfaces:**
- `Task` aliases the validated task model.
- `Harness(results_dir="project_artifacts/results").run(task)` returns a result dictionary with `state`, `result_path` and `result_dir`.
- `Run(root).execute(task)` selects the normal Office or smoke adapter and evaluator.
- `Learn` groups diagnosis and candidate proposal without merging their trust authority.
- `Check` groups verifier and promotion services without allowing either to edit the other.
- `Store(root)` exposes files, logs, skills and rollback under one root.

- [x] Write the failing public API test in `tests/test_simple_harness.py`.
- [x] Run the focused test and observe `ModuleNotFoundError` for `workagent_rsi.data`.
- [x] Add the short-name modules and the `Harness.run` implementation.
- [x] Run `py -3.12 -m pytest -q tests/test_simple_harness.py` and confirm all five focused tests pass.

### Task 2: Normal single-round execution

**Files:**
- Modify: `src/workagent_rsi/run.py`
- Modify: `src/workagent_rsi/skill_runtime.py` only if the normal marker behavior needs a compatibility fix.
- Modify: `src/workagent_rsi/cli.py`
- Test: `tests/test_pipeline_e2e.py`
- Test: `tests/test_simple_harness.py`

**Interfaces:**
- Office tasks use `marker_source="required_text"` by default.
- Smoke tasks continue to use the deterministic text adapter.
- CLI accepts `--results-dir` and keeps `--output` as an exact-path compatibility option.

- [x] Add tests proving normal Office and smoke runs return `SUCCEEDED`.
- [x] Run the focused tests and confirm the normal path is green.
- [x] Route the CLI through `Harness` and remove the hidden `.run-data` output convention.
- [x] Run the CLI against `examples/smoke_task.yaml` and one Office task through the public API.

### Task 3: Unified result directory and documentation

**Files:**
- Modify: `README.md`
- Modify: `src/workagent_rsi/README.md`
- Modify: `docs/project_overview_zh.md`
- Modify: `Agent.md`
- Modify: `project_artifacts/phase3_experiments/README.md`
- Modify: `project_artifacts/phase1_harness/scripts/run_phase1_cases.py`
- Modify: `project_artifacts/phase3_experiments/scripts/run_b0_qualification.py`
- Modify: `project_artifacts/phase3_experiments/scripts/run_b0_office_qualification.py`
- Modify: `project_artifacts/phase3_experiments/scripts/run_e01_e12.py`

**Interfaces:**
- New normal runs write to `project_artifacts/results/<run-id>/`.
- Historical phase directories remain documented as archived evidence; new user-facing examples point to the unified directory.
- Project introduction explains the system with `Harness`, `Run`, `Learn`, `Check`, `Store` and plain-language pipeline steps.
- Experiment scripts default to `project_artifacts/results/experiments/...` without deleting old results.

- [x] Update user-facing documentation and examples with the short names.
- [x] Change new script defaults to the central results root and write a run summary there.
- [x] Search for stale `.run-data` and default phase-specific result instructions.

### Task 4: Full verification and delivery

**Files:**
- Modify: `.gitignore` if needed for the central result directory.
- Test: existing `tests/` suite.

- [x] Run `py -3.12 -m pytest -q --basetemp="$env:TEMP\\workagent-rsi-simple-final"` (the final Windows run used an equivalent workspace-local basetemp because the default temp root is access-restricted).
- [x] Run `py -3.12 -m compileall -q src tests project_artifacts/phase1_harness/scripts project_artifacts/phase3_experiments/scripts`.
- [x] Run one CLI smoke task and one normal Office task, inspect the unified result directory.
- [x] Run `git diff --check` and confirm no generated cache files are staged.
- [ ] Commit the refactor and push the active branch after verification.
