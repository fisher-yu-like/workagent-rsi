# General Office WorkAgent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade normal Harness Office runs to a real Codex/Ollama-driven WorkAgent that creates and edits Excel, Word and PowerPoint files, then qualify its files and exercise an RSI round on real observed evidence.

**Architecture:** Add a focused WorkAgent provider and Office adapter behind the existing `Run -> Orchestrator -> Evaluator` path. Run each model process in a unique workspace, copy in only explicit user inputs, accept only manifest-listed files under `outputs/`, and preserve the full run record in one results directory. Keep the deterministic template adapter explicit for tests; default Office runs to WorkAgent with no silent fallback. After a six-task real baseline, plug the same provider into a frozen WorkAgent-aware RSI evaluator and existing registry/promotion loop.

**Tech Stack:** Python 3.12, Pydantic v2, Codex CLI 0.157.1, Ollama 0.34.4 / `qwen2.5:7b`, openpyxl, python-docx, python-pptx, Microsoft Office COM 16.0, pytest.

**Spec:** `docs/superpowers/specs/2026-09-29-general-office-workagent-design.md`

## Global Constraints

- Keep user inputs unchanged; copy each input into the run workspace and verify its SHA-256 before/after the model run.
- Office-domain `Harness.run()` uses WorkAgent by default; provider/model unavailable or timeout must never trigger template fallback.
- Accept only task-domain-matching `.xlsx`, `.docx`, `.pptx` outputs listed in both the structured response and `deliverables.json`, within `agent_workspace/outputs/`.
- Keep CLI execution, prompt, artifacts, trace, evaluations, and reports for each invocation under one `project_artifacts/results/<run-id>/` directory.
- Codex execution uses `--sandbox workspace-write`; never claim container-grade isolation. If required sandbox arguments are unavailable, fail closed.
- Treat `workspace-write` as write-scope guidance, not a verified read boundary. Until OS-level read isolation is independently demonstrated, pass only project-generated, non-sensitive inputs to the local agent and record this limitation in user-facing documentation.
- Do not send `expected_constraints`, evaluator answers, or promotion thresholds to the WorkAgent prompt.
- Run automated tests only from the existing top-level `tests/`; put pytest temp/cache data under `project_artifacts/results/` and do not create root-level test directories.
- Do not inject deliberately broken prompts or corrupt baseline outputs to create RSI improvement evidence. An unavailable result is not a score.
- Treat the six qualification tasks as a project-generated engineering pilot, not an external benchmark; RSI does not modify model weights.

---

## File Map

| File | Responsibility |
|---|---|
| `src/workagent_rsi/workagent_provider.py` | Typed WorkAgent configuration, versioned skill instructions, structured response, prompt assembly, Codex CLI invocation and process outcome records. |
| `src/workagent_rsi/workagent_office.py` | Office-task adapter: safe input copies, manifests, output containment/format checks, artifact and provider events. |
| `src/workagent_rsi/schemas/agent_response.schema.json` | JSON Schema passed to Codex CLI; does not contain evaluator constraints. |
| `src/workagent_rsi/prompts/office_agent.md` | Versioned general Office task instructions that can be installed into a skill package and tested independently. |
| `src/workagent_rsi/run.py` | Select WorkAgent for ordinary Office tasks; preserve explicit smoke/local/template providers. |
| `src/workagent_rsi/harness.py` | Pass typed WorkAgent options through the public `Harness` API. |
| `src/workagent_rsi/orchestrator.py` | Persist provider events and map timeout/unavailable outcomes to explicit run states. |
| `src/workagent_rsi/cli.py` | Expose WorkAgent as an execution provider and resolve task-file-relative input paths. |
| `src/workagent_rsi/workagent_evaluator.py` | Frozen split evaluator using the real WorkAgent and frozen Office evaluator; stores split-level evidence. |
| `src/workagent_rsi/workagent_experiment.py` | Build a real WorkAgent RSI run using the existing immutable registry, candidate verifier, promotion gate and checkpointed RSI loop. |
| `src/workagent_rsi/candidate_provider.py` | Add a prompt-editing candidate mode while keeping the old marker pilot provider behavior intact. |
| `src/workagent_rsi/rsi_loop.py` | Allow an injected skill model for WorkAgent prompt packages without changing the default marker-pilot behavior. |
| `pyproject.toml` | Include prompt and JSON schema resources in built distributions. |
| `tests/test_workagent_office.py` | One focused top-level test module for config, CLI, input/output safety, integration and WorkAgent RSI. |
| `tests/test_experiment_runner.py` | Preserve legacy RSI behavior while the WorkAgent evaluator is tested independently. |
| `project_artifacts/phase3_experiments/configs/general_office_pilot.json` | Six task prompts, deterministic acceptance constraints, split assignment and generated-input descriptions. |
| `project_artifacts/phase3_experiments/configs/general_office_rsi.json` | Frozen RSI-only develop/regression/hidden/OOD tasks; qualification evidence is reused only when task and evaluator hashes match. |
| `project_artifacts/phase3_experiments/scripts/run_general_office_pilot.py` | Create this invocation's inputs, run six real Harness tasks, check Office COM, and write JSON/Markdown summary beneath results. |
| `project_artifacts/phase3_experiments/scripts/run_workagent_rsi.py` | Invoke the real WorkAgent-aware one-round RSI pilot and preserve every round result. |
| `README.md`, `Agent.md`, `project_artifacts/execution_log.md` | Document the actual default provider, boundaries, qualification outcome, and RSI evidence only after those stages run. |

## Execution and Evidence Commands

Use one unique pytest base directory per command. Generate the timestamp in PowerShell rather than creating any root-level temporary directory:

```powershell
$run = Get-Date -Format 'yyyyMMddTHHmmssZ'
$base = "project_artifacts/results/test-runs/$run"
New-Item -ItemType Directory -Force $base | Out-Null
$env:PYTHONDONTWRITEBYTECODE = '1'
py -3.12 -m pytest -q -p no:cacheprovider --basetemp=$base tests
```

Run the six real Office tasks only after tests and capability probes pass:

```powershell
py -3.12 project_artifacts/phase3_experiments/scripts/run_general_office_pilot.py `
  --provider codex --backend ollama --model qwen2.5:7b --verify-com
```

Run RSI only after all six create/edit pilot tasks have completed and are independently inspected:

```powershell
py -3.12 project_artifacts/phase3_experiments/scripts/run_workagent_rsi.py `
  --provider codex --backend ollama --model qwen2.5:7b --rounds 1
```

Both scripts refuse an existing invocation directory. They write all runs/reports to a unique child of `project_artifacts/results/qualification/general-office/`; no manually marked score files are created.

---

### Task 1: Add typed WorkAgent configuration and response contracts

**Files:**
- Create: `src/workagent_rsi/workagent_provider.py`
- Create: `src/workagent_rsi/schemas/agent_response.schema.json`
- Create: `tests/test_workagent_office.py`

**Interfaces:**
- Produce `WorkAgentConfig`, `AgentResponse`, `ProviderOutcome` and `build_agent_response_schema()`.
- `WorkAgentConfig` defaults: `model="qwen2.5:7b"`, `executable="codex"`, `timeout_seconds=600`, `max_output_files=8`, `max_artifact_bytes=104857600`, `verify_com=True`.
- `AgentResponse` fields: `status: Literal["completed", "failed"]`, `deliverables: list[str]`, `summary: str`, `input_files_used: list[str]`.

- [ ] **Step 1: Write a failing validation test**

```python
import pytest
from pydantic import ValidationError

from workagent_rsi.workagent_provider import AgentResponse, WorkAgentConfig

def test_workagent_config_has_bounded_local_defaults():
    config = WorkAgentConfig()
    assert (config.model, config.timeout_seconds, config.max_output_files) == (
        "qwen2.5:7b", 600, 8
    )
    assert config.max_artifact_bytes == 100 * 1024 * 1024

def test_agent_response_rejects_unknown_status_and_absolute_paths():
    with pytest.raises(ValidationError):
        AgentResponse.model_validate({"status": "maybe", "deliverables": [], "summary": "x", "input_files_used": []})
```

- [ ] **Step 2: Run the focused test and verify it fails because the contracts do not exist**

Run: `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t1 tests/test_workagent_office.py -k 'config_has_bounded or response_rejects'`

Expected: collection fails on missing `workagent_provider` import.

- [ ] **Step 3: Implement only the Pydantic contracts and matching schema resource**

Use `ConfigDict(extra="forbid")`; validate positive file/time limits; response paths are relative POSIX paths and reject drive/UNC/rooted paths, `..`, and empty path components. Do not add process execution in this task.

- [ ] **Step 4: Re-run the focused tests and format/diff checks**

Run the command from Step 2 and `git diff --check`.

Expected: the two contract tests pass and no whitespace errors appear.

- [ ] **Step 5: Commit the contract unit**

```powershell
git add src/workagent_rsi/workagent_provider.py src/workagent_rsi/schemas/agent_response.schema.json tests/test_workagent_office.py
git commit -m "feat: define WorkAgent Office contracts"
```

### Task 2: Implement Codex CLI invocation and evidence capture

**Files:**
- Modify: `src/workagent_rsi/workagent_provider.py`
- Modify: `tests/test_workagent_office.py`

**Interfaces:**
- `CodexOfficeProvider.command(workspace: Path, response_path: Path, schema_path: Path) -> list[str]` returns the explicit Ollama/workspace-write CLI arguments.
- `CodexOfficeProvider.run(prompt: str, workspace: Path, record_root: Path) -> ProviderOutcome` saves prompt, stdout, stderr, structured response, command, hash, times, exit code and status.

- [ ] **Step 1: Write tests for exact command policy and stdin prompt behavior**

```python
def test_provider_uses_ollama_ephemeral_workspace_write_and_schema(tmp_path):
    provider = CodexOfficeProvider(WorkAgentConfig())
    command = provider.command(tmp_path, tmp_path / "agent_response.json", provider.schema_path)
    assert command[:2] == ["codex", "exec"]
    assert command[command.index("--sandbox") + 1] == "workspace-write"
    assert command[command.index("--local-provider") + 1] == "ollama"
    assert command[command.index("--model") + 1] == "qwen2.5:7b"
    assert "--dangerously-bypass-approvals-and-sandbox" not in command
    assert "--output-schema" in command and "--ephemeral" in command
```

- [ ] **Step 2: Run the focused test and verify it fails on the missing provider method**

Run: `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t2 tests/test_workagent_office.py -k provider_uses_ollama`.

Expected: import or attribute failure for `CodexOfficeProvider.command`.

- [ ] **Step 3: Build the command and a deterministic prompt**

Use `codex exec --ignore-user-config --oss --local-provider ollama --model <model> --ephemeral --sandbox workspace-write --json --output-schema <schema> --output-last-message <unique-response-in-workspace> --cd <workspace> -`. Pass prompt over subprocess stdin (`input=prompt`) so it is not embedded in process arguments. Give each invocation a unique raw response filename inside `agent_workspace`; after successful parsing, preserve the canonical `agent_workspace/agent_response.json` and copy a run-evidence response into the result root. Never expose a no-sandbox fallback.

- [ ] **Step 4: Add one process-result test for success and one for timeout/unavailable**

Assert successful stdout/stderr and response are written under the run; assert `TimeoutExpired` yields `timeout`; assert `FileNotFoundError` yields `unavailable`; assert all returned process records use `model_identity="ollama:qwen2.5:7b"` from configuration, not response self-claims. Timeout captures and writes partial stdout/stderr before returning.

- [ ] **Step 5: Run the provider tests and commit**

Run: `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t2 tests/test_workagent_office.py -k provider`.

```powershell
git add src/workagent_rsi/workagent_provider.py tests/test_workagent_office.py
git commit -m "feat: run Codex with local Office model"
```

### Task 3: Implement safe input copy, prompt assembly, and output acceptance

**Files:**
- Create: `src/workagent_rsi/workagent_office.py`
- Create: `src/workagent_rsi/prompts/office_agent.md`
- Modify: `src/workagent_rsi/workagent_provider.py`
- Modify: `tests/test_workagent_office.py`

**Interfaces:**
- `copy_task_inputs(task: TaskSpec, workspace: Path, input_base: Path) -> dict` copies only explicit regular Office files into `inputs/`, computes original/copy SHA-256, and writes `input_manifest.json` without original absolute paths.
- `build_task_prompt(task: TaskSpec, input_manifest: dict, agent_instructions: str) -> str` includes instruction/domain/copied input names and output rules but excludes `expected_constraints`.
- `validate_deliverables(task: TaskSpec, workspace: Path, response: AgentResponse, config: WorkAgentConfig) -> list[Path]` checks response/manifest equality, containment, exact suffix, file count and byte limits.

- [ ] **Step 1: Write input-isolation tests using real temporary files**

Create a real `.xlsx` through openpyxl, hash it, call `copy_task_inputs`, then assert the copy hash matches and the source hash is unchanged. Add a second test that a Word file cannot be supplied to an Excel task, and a third that directories/symlinks are rejected.

- [ ] **Step 2: Write prompt-separation and output-containment tests**

```python
def test_task_prompt_does_not_expose_evaluator_constraints(tmp_path):
    task = TaskSpec(task_id="pilot-1", domain="excel", instruction="Build an expense workbook",
                    expected_constraints={"required_cells": {"Summary!B2": 999}})
    prompt = build_task_prompt(task, {"files": []}, "Use clear sheet names")
    assert "Build an expense workbook" in prompt
    assert "999" not in prompt and "expected_constraints" not in prompt
```

Also assert `outputs/../outside.xlsx`, absolute paths, symlinks, unlisted outputs, mismatched `.docx`, empty files, and size/count overflow are rejected before yielding artifact events.

- [ ] **Step 3: Run focused tests to confirm failure precedes implementation**

Run: `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t3 tests/test_workagent_office.py -k 'input or prompt or deliverable'`.

Expected: import errors naming the missing functions in `workagent_office`.

- [ ] **Step 4: Implement input copy and prompt construction**

Resolve paths against the configured input base. Reject UNC paths, symbolic links, directories, missing files, unsupported suffixes and cross-domain formats. Copy to `agent_workspace/inputs/0001-<safe-name>`, record a privacy-safe manifest, and recompute source hashes after provider exit. Store the exact prompt as `prompt.md` in the run evidence.

- [ ] **Step 5: Implement schema and filesystem-backed output validation**

Require `agent_response.json` and `agent_workspace/deliverables.json` to parse and list identical relative paths; reject all paths that resolve outside `outputs/`; require ordinary non-empty files with matching suffix and configured size/count limits. Do not scan for alternate output files when the manifest is missing.

- [ ] **Step 6: Run safety tests and commit**

Run the focused command in Step 3; commit with message `feat: validate WorkAgent Office inputs and outputs`.

### Task 4: Connect the adapter to the existing Harness event/evaluator path

**Files:**
- Modify: `src/workagent_rsi/workagent_office.py`
- Modify: `src/workagent_rsi/orchestrator.py`
- Modify: `src/workagent_rsi/run.py`
- Modify: `src/workagent_rsi/harness.py`
- Modify: `tests/test_workagent_office.py`

**Interfaces:**
- `WorkAgentOfficeAdapter.execute(task, skill_id)` emits `started`, `input_manifest`, `provider_output`, validated `artifact` events and exactly one terminal `failure`/`unavailable` event when unsuccessful.
- `Run(..., execution_provider="workagent", workagent_config=config, agent_instructions=...)` uses the real provider and `OfficeArtifactEvaluator`.
- A normal Office task defaults to `workagent`; non-Office smoke tasks keep the existing default smoke adapter.

- [ ] **Step 1: Write failing integration tests against public `Harness.run()`**

Inject a deterministic provider runner that creates a genuine `.xlsx` with openpyxl, writes both manifests, and returns a successful Codex-compatible `CompletedProcess`. Assert `Harness` returns `SUCCEEDED`, the artifact is in the run's artifact store, trace has provider and model identity, and `result.json` references the same run. Add a regression test where the injected provider is unavailable and assert result is `UNAVAILABLE` with no template artifact.

- [ ] **Step 2: Verify these tests fail because `workagent` is not a supported provider**

Run: `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t4 tests/test_workagent_office.py -k harness`.

- [ ] **Step 3: Add `workagent` provider selection and pass WorkAgent events through**

Keep `local_office` and `com` explicit. Update Orchestrator's terminal-state map so `unavailable` and `timeout` cannot proceed to evaluator success. Ensure all artifacts are copied by the existing `ArtifactStore` and every event is persisted.

- [ ] **Step 4: Update legacy Office tests to select the deterministic provider explicitly**

Update tests that currently rely on implicit `local_office` to pass `execution_provider="local_office"`; do not weaken their template assertions. Confirm default smoke tasks are unchanged.

- [ ] **Step 5: Run Harness/Office focused regression and commit**

Run: `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t4 tests/test_workagent_office.py tests/test_simple_harness.py tests/test_office_adapter.py tests/test_office_evaluator.py`.

Commit the integration after all selected tests pass.

### Task 5: Expose the provider through the YAML CLI and package resources

**Files:**
- Modify: `src/workagent_rsi/cli.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_workagent_office.py`
- Modify: `README.md`

- [ ] **Step 1: Add CLI parser tests**

Assert `--execution-provider workagent` is accepted; assert no provider flag chooses WorkAgent for an Office task; assert relative `input_files` resolve against the task YAML's parent rather than the shell's current directory.

- [ ] **Step 2: Run CLI tests and verify expected failures**

Run: `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t5 tests/test_workagent_office.py -k cli`.

- [ ] **Step 3: Pass resolved input base and WorkAgent config through the public API**

Add `workagent` to the provider choices without changing the existing YAML task shape. Before calling Harness, resolve each relative input path against `args.task.resolve().parent`; do not infer the base from the run directory.

- [ ] **Step 4: Package the prompt/schema resources and document supported operations**

Add setuptools package-data configuration for `prompts/*.md` and `schemas/*.json`. README examples show a real Office creation/edit task and state local model, no-fallback behavior, supported suffixes and isolation limits.

- [ ] **Step 5: Verify package import and CLI tests; commit**

Run the CLI focused tests, `py -3.12 -m compileall -q src/workagent_rsi`, and `git diff --check`; then commit.

### Task 6: Build the six-task real Office qualification suite

**Files:**
- Modify: `tests/test_workagent_office.py`
- Create: `project_artifacts/phase3_experiments/configs/general_office_pilot.json`
- Create: `project_artifacts/phase3_experiments/scripts/run_general_office_pilot.py`
- Modify: `project_artifacts/execution_log.md`

**Pilot coverage:**
- Excel: create a quarterly revenue workbook with formula-backed totals and a named summary sheet; edit a generated input transaction workbook into a summary workbook while preserving its source data.
- Word: create a project status report with specified sections and required action text; edit a supplied draft into the requested final structure while preserving a specified source fact.
- PowerPoint: create a three-slide briefing with specified slide titles and takeaway; edit a supplied deck while preserving its slide count and requested content.

The JSON config separates each user instruction from evaluator-only constraints. For example:

```json
{
  "task_id": "excel-create",
  "domain": "excel",
  "split": "evolve",
  "instruction": "Create a Summary sheet with Q1, Q2 and Q3 revenue, a total row, and a SUM formula in B5.",
  "input_files": [],
  "expected_constraints": {
    "required_sheets": ["Summary"],
    "required_cells": {"Summary!A1": "Quarter", "Summary!B2": 120, "Summary!B3": 150},
    "required_formulas": {"Summary!B5": "=SUM(B2:B4)"}
  }
}
```

Run all six qualification cases through Harness once. For RSI, use a separate 12-task frozen matrix: three create tasks in `develop`, three original input-edit tasks in `regression`, three held-out `hidden` tasks, and three alternate-layout `ood_transfer` tasks. Keep this small project-generated matrix as engineering evidence, not a statistical benchmark. During split evaluation, the WorkAgent receives each task's user instruction, including hidden/OOD task instructions, but never `expected_constraints` or evaluator labels. The candidate generator receives only develop diagnoses; it never receives hidden/OOD instructions, constraints, or per-task outcome rows.

- [ ] **Step 1: Add characterization tests for the pilot constraints**

For each domain, write one test with an openpyxl/python-docx/python-pptx-created file satisfying the constraint and one task constraint that the same file does not satisfy. Cover the checks already supported by `OfficeArtifactEvaluator`: required Excel sheets/cells/formula strings, Word headings/styles/text, and PowerPoint slide count/shape text/geometry.

- [ ] **Step 2: Run evaluator characterization tests**

Run `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t6 tests/test_workagent_office.py -k evaluator`; these tests should pass against the current evaluator. They freeze the exact pilot criteria before any live model run.

- [ ] **Step 3: Freeze evaluator identity and keep scope fixed**

Use the current `OfficeArtifactEvaluator` without changes because its supported constraints cover the six tasks. Record its source hash in the pilot config. If a task cannot be described using the existing checks, revise the task to use a supported objective criterion; do not expand the evaluator as an unreviewed part of this pilot.

- [ ] **Step 4: Define task config and generate source inputs inside each invocation**

Store user instructions separately from `expected_constraints`. Generate source xlsx/docx/pptx under the invocation's result directory; include source hashes and `project-generated` provenance. Do not commit task output artifacts outside results.

- [ ] **Step 5: Implement the pilot runner**

The runner probes all three COM applications before starting; runs each task once through public `Harness`; enforces unique run IDs; verifies each output using the Office evaluator and explicit COM reopen; checks input hashes before/after; writes `summary.json`, per-task `result.json`, `qualification_report.md`, prompts, traces and Office files below one invocation directory. It returns nonzero on a real failed qualification while preserving all partial evidence.

- [ ] **Step 6: Run qualification tests, then run all six real creation/edit tasks**

First run only the tests in one result-scoped basetemp; then invoke the six-task pilot command once. Do not fabricate, mutate or rerun a task merely to obtain a success. If a task fails naturally, retain it; after a code/prompt fix, use a fresh invocation with the same frozen task and disclose the retry lineage.

- [ ] **Step 7: Review outputs and commit code/config/docs, not ignored result binaries**

Check six output suffixes, each result/trace/evaluation, COM version, source hashes, workspace cleanup policy and root cleanliness. Add only implementation/config/documentation files to Git; results remain in `project_artifacts/results/`.

### Task 7: Make RSI operate on WorkAgent skill instructions and real Office outputs

**Files:**
- Modify: `src/workagent_rsi/workagent_provider.py`
- Create: `src/workagent_rsi/workagent_evaluator.py`
- Create: `src/workagent_rsi/workagent_experiment.py`
- Modify: `src/workagent_rsi/workagent_office.py`
- Modify: `src/workagent_rsi/candidate_provider.py`
- Modify: `src/workagent_rsi/rsi_loop.py`
- Modify: `tests/test_workagent_office.py`
- Create: `project_artifacts/phase3_experiments/configs/general_office_rsi.json`

**Interfaces:**
- `WorkAgentSkill(BaseModel)` in `workagent_provider.py` contains versioned `instructions: str` and forbids extra fields.
- `WorkAgentFrozenEvaluator.evaluate_split(tasks, split_name, config: WorkAgentSkill, contract, result_root, *, reveal_per_task=False)` runs the actual Harness WorkAgent. It returns a score only when every task has a terminal evaluation; unavailable/timeouts produce `status="incomplete"`, retain unavailable records, and omit numeric scores. Only `develop` may reveal per-task rows to the RSI controller; `regression`, `hidden`, and `ood_transfer` remain aggregate-only in candidate-facing reports. Full evidence remains in the protected result directory.
- `WorkAgentCandidateProvider` proposes only bounded `{"instructions": "..."}` patches to `skill.json`; the existing marker candidate prompt/provider remains unchanged for old experiments.
- `WorkAgentExperimentRunner.run(tasks_by_split, initial_skill, provider, output_root, *, rounds=1)` creates immutable registry state and invokes `RSILoop` with the WorkAgent skill model/evaluator.

- [ ] **Step 1: Write a frozen-evaluator test with a deterministic real-file provider**

Build one task per Office domain in `tmp_path`; assert `WorkAgentFrozenEvaluator` uses `WorkAgentSkill.instructions`, stores one real Office artifact and trace per task, and rejects changed task/evaluator hashes.

- [ ] **Step 2: Run the test to observe the missing evaluator**

Run: `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/plan-t7 tests/test_workagent_office.py -k frozen_evaluator`.

- [ ] **Step 3: Generalize RSI loop skill parsing through an injected model**

Add `skill_model: type[BaseModel] = PilotSkillConfig` to `RSILoop`; use that model when loading champion and candidate packages. Existing call sites keep the default and all old experiment results remain reproducible.

- [ ] **Step 4: Implement the WorkAgent frozen evaluator and candidate prompt profile**

The split evaluator verifies canonical task split/evaluator hashes before any model runs, stores each real run in its split directory, and aggregates only terminal evaluations. A timeout/unavailable task makes the split incomplete, not a zero score; return `status="incomplete"` and omit `score` if any task is incomplete. Before diagnosis or candidate generation, `RSILoop` must stop without promotion when any required baseline split is incomplete; after candidate verification, any incomplete candidate split also stops before metrics/promotion. Candidate provider may edit only `instructions`; protected checks/evaluator/provider remain outside candidate workspace. Only develop diagnoses/rows may reach candidate generation. The separate RSI config supplies tasks for `develop`, `regression`, `hidden` and `ood_transfer`; the six qualification tasks alone are insufficient for these gates.

- [ ] **Step 5: Stop without proposing edits when there is no observed failure**

Before calling the candidate provider, detect an empty diagnosis list for WorkAgent RSI. Persist `status="no_candidate_needed"`, retain the champion, and do not invent a failure. Add a test proving the candidate provider was not called. Keep existing promotion gates unchanged.

- [ ] **Step 6: Add RSI tests for target restrictions, incomplete runs and real cost evidence**

Use the deterministic test provider to propose an `instructions` patch and test verifier/registry evidence and rollback. Test that an unavailable baseline and an unavailable candidate evaluation both stop without promotion or numeric score. Test that hidden/OOD per-task rows are not revealed to candidate-facing reports or candidate generation. For WorkAgent RSI, compute cost delta from completed baseline/candidate wall-time totals; leave token/tool counts unavailable if the CLI does not report them. Never reuse the existing legacy placeholder cost; preserve the legacy metric path for existing experiments.

- [ ] **Step 7: Run old RSI regressions and WorkAgent RSI tests; commit**

Run `tests/test_workagent_office.py`, `tests/test_experiment_runner.py`, `tests/test_rsi_loop.py`, `tests/test_promotion.py`, and `tests/test_verifier.py` with a results-scoped basetemp. Commit only after legacy tests remain green.

### Task 8: Run one real RSI pilot and write the user-facing report

**Files:**
- Create: `project_artifacts/phase3_experiments/scripts/run_workagent_rsi.py`
- Modify: `README.md`
- Modify: `Agent.md`
- Modify: `project_artifacts/execution_log.md`
- Runtime output: `project_artifacts/results/qualification/general-office/<invocation>/`

- [ ] **Step 1: Freeze the RSI task matrix, source-input hashes, evaluator hash and baseline skill hash**

Load `general_office_rsi.json`, generate any held-out inputs inside this invocation, and write `contract.json` with project-generated provenance, fixed seed, all split hashes, evaluator hash, provider identity, timeouts and promotion thresholds. Keep `expected_constraints` out of agent prompt construction. Do not reuse qualification outputs unless task, input and evaluator hashes match exactly.

- [ ] **Step 2: Require a completed six-task baseline before starting RSI**

Script preflight checks that all six create/edit pilot tasks have persisted terminal results and input hash records, with at least one successful create and one successful edit in each of the three formats. If a task is unavailable/timed out, or a format lacks a successful create/edit task, write a concise block reason and refuse the RSI stage without deleting baseline evidence. A genuine failed task remains visible and may proceed to RSI only when this minimum evidence condition holds; do not relabel it or erase it.

- [ ] **Step 3: Run one bounded RSI round using the local Codex/Ollama candidate generator**

Run one real round on the frozen project-generated task splits. Do not seed synthetic diagnoses or fabricate failures. If the baseline has no observed gap, record no eligible candidate and stop with champion unchanged. Candidate verification, Office evaluator, cross-domain regressions and promotion all run on actual model-produced Office files.

- [ ] **Step 4: Preserve round and aggregate reports**

Keep provider stdout/stderr, candidate diff, verifier checks, baseline/candidate split reports, decisions, registry lineage, rollback point, wall-time/disk/token-availability fields, `summary.json`, `analysis.json` and a Chinese `qualification_report.md` under one invocation directory. Unreported token usage stays unavailable.

- [ ] **Step 5: Update project documentation from observed results only**

Document supported tasks, local provider selection, evidence links, exact pass/failed/unavailable counts, limitations and any no-candidate outcome. Update `Agent.md` and `execution_log.md` to separate implemented code, real results, unavailable channels and remaining external-data gate.

- [ ] **Step 6: Review all artifacts, check no template fallback and run final tests**

Verify every listed file exists; all three Office packages load with their libraries; COM 16.0 opens them; input hashes are unchanged; test artifacts stayed below results; `git diff --check`, `compileall` and the full pytest suite pass. Then commit and push the implementation/documentation branch to `origin/codex/closed-loop-rsi` as previously requested.

---

## Self-Review

- **Spec coverage:** creation/edit support, no input overwrite, WorkAgent default/no fallback, local provider/model identity, safe input copies, schema and deliverable manifests, path/type/size checks, run evidence, COM opening, six-task baseline, no manual labels, frozen evaluator, RSI candidate verification/promotion, no-result handling, clean tests, and external-benchmark claim boundaries each map to Tasks 1–8.
- **Scope:** the main provider and the WorkAgent-backed RSI extension are coupled through the same `WorkAgentSkill`, evaluator and frozen task set; keeping them in one sequential plan avoids implementing RSI against the current marker-only evaluator.
- **Failure/evidence policy:** real model errors are retained under results; deliberately broken prompts and artifacts are not part of pilot runs. Unit tests exercise error handling through subprocess results without polluting Office qualification scores.
- **Legacy compatibility:** every change to `RSILoop`, `PromotionController`, default `Run` selection and candidate provider has a task to preserve existing marker-pilot behavior.
- **Root cleanliness:** only one top-level test module is added; test temporaries and all runtime files are directed to `project_artifacts/results/`.
- **Incomplete evaluation:** WorkAgent-specific incompleteness is handled before score aggregation and promotion; unavailable results are neither zero scores nor promotion evidence.
- **Split completeness:** six-task file qualification and the separate RSI split matrix serve different purposes; hidden/OOD gates cannot use missing evidence.
- **Isolation boundary:** workspace-write is not described as a verified read-deny sandbox; live execution uses only project-generated, non-sensitive inputs until an OS-level boundary is verified.

## Execution outcome (2026-09-30)

- Tasks 1–7 implementation is committed and independently reviewed. Task 6's two real qualification invocations both remain 0/6; this is recorded failure evidence, not a passing qualification.
- Task 8's preflight/reporting code is implemented and reviewed. The final preflight is `project_artifacts/results/qualification/general-office/20260929T212754Z-45c2bcc1/`; it refused to start RSI or candidate generation because the latest baseline has 0 successful, 6 failed, and 0 unavailable tasks. Generated source inputs passed Office-library reopen, unchanged-hash, and COM 16.0 checks, but no WorkAgent deliverables exist to validate.
- The real RSI round remains not run by design until a fresh six-task baseline has a successful create and edit in Excel, Word, and PowerPoint. No external benchmark or model-weight training result is claimed.
- Final verification: fresh full suite `200 passed, 3 skipped` using `project_artifacts/results/test-runs/20260929T214553Z-final/`; `compileall` and Git whitespace checks passed. Test and bytecode cache output stayed under `project_artifacts/results/`.
