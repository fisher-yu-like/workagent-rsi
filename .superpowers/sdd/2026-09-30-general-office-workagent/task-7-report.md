# Task 7 implementation report

## Scope
Implemented WorkAgent RSI integration while preserving the legacy marker RSI path. Added the versioned `WorkAgentSkill` model, frozen evaluator for real Harness Office executions, bounded instruction-only candidate provider profile, WorkAgent experiment runner, RSI model injection, incomplete/no-candidate gates, hidden/OOD aggregate-only reporting, and measured wall-time cost evidence.

## Files changed
- `src/workagent_rsi/workagent_provider.py`: added strict versioned `WorkAgentSkill`.
- `src/workagent_rsi/workagent_evaluator.py`: added hash-checked frozen real-artifact evaluator; incomplete runs retain rows/evidence and omit scores.
- `src/workagent_rsi/workagent_experiment.py`: added immutable registry/contract runner for all four RSI splits.
- `src/workagent_rsi/workagent_office.py`: accepts `WorkAgentSkill` instructions in prompt construction.
- `src/workagent_rsi/candidate_provider.py`: added instruction-only WorkAgent candidate prompt profile.
- `src/workagent_rsi/rsi_loop.py`: injected skill model; added incomplete baseline/candidate stops, no-candidate stop, bounded WorkAgent patch validation, develop-only diagnosis input, and measured cost delta.
- `tests/test_workagent_office.py`: deterministic real-file evaluator, no-diagnosis, unavailable baseline/candidate, hidden/OOD, verification and rollback tests.
- `project_artifacts/phase3_experiments/configs/general_office_rsi.json`: four-split RSI config.

## Verification commands/results
- `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t7 tests/test_workagent_office.py -k frozen_evaluator` — initial red check before the test existed: 93 deselected, exit 1 (no selected tests).
- `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t7 tests/test_workagent_office.py -k frozen_evaluator` — 1 passed.
- `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t7 tests/test_workagent_office.py -k 'frozen_evaluator or workagent_rsi'` — 3 passed.
- `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t7 tests/test_workagent_office.py -k workagent_rsi` — 4 passed.
- `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t7-full tests/test_workagent_office.py tests/test_experiment_runner.py tests/test_rsi_loop.py tests/test_promotion.py tests/test_verifier.py` — 104 passed, 3 skipped.
- `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t7-final tests/test_workagent_office.py tests/test_experiment_runner.py tests/test_rsi_loop.py tests/test_promotion.py tests/test_verifier.py` — 104 passed, 3 skipped.
- `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t7-commit tests/test_workagent_office.py tests/test_experiment_runner.py tests/test_rsi_loop.py tests/test_promotion.py tests/test_verifier.py` — 104 passed, 3 skipped in 33.16s after final changes.
- `py -3.12 -m compileall -q src/workagent_rsi` — passed.
- `git add -- src/workagent_rsi/workagent_provider.py src/workagent_rsi/workagent_evaluator.py src/workagent_rsi/workagent_experiment.py src/workagent_rsi/workagent_office.py src/workagent_rsi/candidate_provider.py src/workagent_rsi/rsi_loop.py tests/test_workagent_office.py project_artifacts/phase3_experiments/configs/general_office_rsi.json .superpowers/sdd/2026-09-30-general-office-workagent/task-7-report.md` — Task 7 sources staged; ignored report required force-add.
- `git add -f .superpowers/sdd/2026-09-30-general-office-workagent/task-7-report.md` — report staged.
- `git commit -m "Implement WorkAgent RSI integration"` — created `6bb43a9` (amended only to include this command record).

No real model qualification or RSI runs were launched; all WorkAgent RSI tests use deterministic providers.

## Concerns
The repository already contained unrelated modifications in the design spec and execution log; they were not altered. The deterministic config uses minimal generated tasks and is intended for RSI contract/testing, not qualification evidence.
