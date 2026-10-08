# Office Qualification Gate Unblock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将通用 Office WorkAgent 从当前 `0/6` 失败状态推进到可审计的六项资格运行，并在所有安全、格式、内容和 COM 证据通过后解除 RSI 前置门禁。

**Status:** Completed on 2026-10-01. The six-task baseline passed in
`20261001T053355Z-f2d4995e`; the guarded local-model RSI round completed in
`20261001T065932Z-9faf97ae` and accepted champion `1.1.0`. Evidence remains
project-generated and the external dataset/license gate remains closed.

**Architecture:** 保留现有 `Harness -> WorkAgent provider -> Office evaluator -> COM reopen -> qualification summary` 闭环，不降低 evaluator、输入哈希、输出路径和 fail-closed 规则。先用一个 Excel create 任务定位 provider/tool 执行问题，再按 Excel、Word、PowerPoint 的 create/edit 顺序扩大运行；每一阶段都在独立的 `project_artifacts/results/` run 目录留存 prompt、command、stdout/stderr、provider record、artifact hash、evaluation 和 COM 证据。

**Tech Stack:** Python 3.12、pytest、Codex CLI 0.157.1、Ollama 0.34.4、`qwen2.5:7b`、openpyxl、python-docx、python-pptx、Windows Office 16.0 COM。

**Spec:** `workagent-rsi.md`, `Agent.md`, `docs/superpowers/specs/2026-09-29-general-office-workagent-design.md`

## Global Constraints

- 不伪造 Office 文件、provider trace、评分、COM 结果或成功运行。
- 不把 `unavailable`、`timeout` 或 CLI 环境错误计为数值分数。
- 不用模板生成器替代 WorkAgent；WorkAgent 失败时保持失败并保留证据。
- 输入原件只读复制，运行前后源文件和 staged copy 的 SHA-256 必须一致。
- 输出只能是对应域的真实 `.xlsx`、`.docx` 或 `.pptx`，并且必须列在 `deliverables.json` 中。
- 所有 pytest 临时目录放在 `project_artifacts/results/test-runs/`，不在主目录增加测试目录。
- 每次真实运行使用新的结果目录；不得覆盖历史 qualification 证据。
- 当前两个用户已有未提交文件不纳入本计划提交：`docs/superpowers/specs/2026-09-29-general-office-workagent-design.md`、`project_artifacts/execution_log.md`。

---

### Task 1: 固化环境与门禁前置证据

**Files:**
- Read: `src/workagent_rsi/office_capabilities.py`
- Read: `project_artifacts/phase3_experiments/scripts/check_office_capabilities.py`
- Create: `project_artifacts/results/qualification/capabilities/<timestamp>/capability_report.json`
- Modify: `project_artifacts/execution_log.md` (only after a verified run, preserving existing user edits)

**Interfaces:**
- Consumes: local Python 3.12, `codex`, `ollama`, Office COM registrations.
- Produces: immutable environment report with executable versions, model availability, COM versions, and explicit unavailable reasons.

- [x] **Step 1: Run the capability probe**

  Run:

  ```powershell
  py -3.12 project_artifacts/phase3_experiments/scripts/check_office_capabilities.py `
    --output-root project_artifacts/results/qualification/capabilities
  ```

  Expected: Excel, Word and PowerPoint report `available` with COM version `16.0`; `codex --version`, `ollama --version`, and `ollama list` show the configured executable and `qwen2.5:7b`.

- [x] **Step 2: Confirm that environment failure is not silently scored**

  Run the existing focused regression suite with a project-local temp directory:

  ```powershell
  py -3.12 -m pytest -q --basetemp=project_artifacts/results/test-runs/20260930-office-gate-preflight tests/test_office_capabilities.py tests/test_workagent_final_review.py -k "com or unavailable or timeout"
  ```

  Expected: all selected tests pass; no `UNAVAILABLE` result contains a numeric `score`.

- [x] **Step 3: Record the preflight result**

  Append one human-readable entry to `project_artifacts/execution_log.md` containing the run directory, tool versions, COM versions, and whether the provider/model is available. Do not claim qualification success here.

### Task 2: Diagnose and repair one real WorkAgent task

**Files:**
- Read: `src/workagent_rsi/workagent_provider.py`
- Read: `src/workagent_rsi/workagent_office.py`
- Read: `src/workagent_rsi/prompts/office_agent.md`
- Modify: `project_artifacts/phase3_experiments/scripts/run_general_office_pilot.py` for an optional exact `--task` selector; modify provider/prompt only if run evidence proves a defect
- Test: `tests/test_workagent_office.py` or an existing top-level test file; do not create a new test directory

**Interfaces:**
- Consumes: frozen `excel-create` task from `project_artifacts/phase3_experiments/configs/general_office_pilot.json`.
- Produces: one completed provider record, `agent_response.json`, `deliverables.json`, real `outputs/quarterly_revenue.xlsx`, evaluator result, and COM reopen result. With no `--task`, the existing frozen six-task behavior and acceptance remain unchanged.

- [x] **Step 1: Run only `excel-create` through the public WorkAgent path**

  Add an optional `--task` argument accepting only one of the six frozen IDs. The selected task still runs through `Harness`, evaluator, source hash verification, and COM; only the selected task is written to its unique invocation. The unfiltered default still runs the complete six-task matrix.

  Expected failure evidence must identify which boundary failed: provider unavailable/timeout, provider completed without response, response schema failure, missing manifest, evaluator failure, or COM reopen failure.

- [x] **Step 2: Inspect provider evidence before editing code**

  Read the run's `provider_records/command.json`, `prompt.md`, `provider.stderr.txt`, `provider.stdout.jsonl`, `provider_record.json`, and workspace file listing. Confirm whether Codex invoked local tools and whether the configured `--output-last-message` file was written.

- [x] **Step 3: Add a regression test for the observed boundary**

  The test must reproduce the concrete failure using a controlled subprocess/provider fixture and assert the required outcome. Examples: a missing structured response remains `failed`; an explicit CLI/model capability error is `unavailable`; a valid response with a real workbook is accepted; a response without a matching manifest is rejected.

- [x] **Step 4: Implement the smallest repair**

  Preserve the existing command safety, workspace isolation, schema validation, response/manifest agreement, input hash checks, and fail-closed behavior. Do not add a template fallback or relax the required Office artifact checks.

- [x] **Step 5: Verify the single task end to end**

  Run the new regression test, then the real `excel-create` task once. Acceptance requires: provider status `completed`; exactly one listed `.xlsx`; openpyxl validation of sheet/cells/formula; evaluator `passed=true`; COM `available`; harness state `SUCCEEDED`; numeric score present only after these checks.

### Task 3: Qualify Excel, then Word and PowerPoint

**Files:**
- Read: `project_artifacts/phase3_experiments/configs/general_office_pilot.json`
- Read: `project_artifacts/phase3_experiments/scripts/run_general_office_pilot.py`
- Create: one new result directory under `project_artifacts/results/qualification/general-office/`
- Modify: `project_artifacts/execution_log.md` after each verified run

**Interfaces:**
- Consumes: the repaired provider path and frozen six-task matrix.
- Produces: six task rows with provider, evaluator, artifact hash, input hash, and COM evidence.

- [x] **Step 1: Run the two Excel tasks**

  Run create and edit tasks in a fresh invocation. Require both outputs to be real `.xlsx` files and require the edit task to preserve the original Transactions cells and source hash.

- [x] **Step 2: Run the two Word tasks**

  Require real Heading 1/Heading 2 styles, exact required text, source preservation for the edit task, python-docx reopen, evaluator pass, and COM reopen.

- [x] **Step 3: Run the two PowerPoint tasks**

  Require exact slide counts, visible required phrases, in-bounds non-overlapping shapes, python-pptx reopen, evaluator pass, and COM reopen.

- [x] **Step 4: Check the six-task summary**

  Acceptance is exactly `success_count=6`, `failure_count=0`, `unavailable_count=0`, every row `SUCCEEDED`, every row has a non-empty artifact SHA-256, `evaluation_passed=true`, `com_ok=true`, `input_hashes_ok=true`, and no output path escapes its run directory.

### Task 4: Re-run the RSI preflight with the qualified baseline

**Files:**
- Read: `project_artifacts/phase3_experiments/scripts/run_workagent_rsi.py`
- Read: `project_artifacts/phase3_experiments/configs/general_office_rsi.json`
- Create: new preflight directory under `project_artifacts/results/qualification/general-office/`
- Modify: `project_artifacts/execution_log.md`

**Interfaces:**
- Consumes: the immutable six-task qualification summary and all artifact/evaluator hashes.
- Produces: `qualification_report.md`, `source_office_validation.json`, preflight status, and explicit `rsi_started`/`candidate_started` flags.

- [x] **Step 1: Validate baseline identity and hashes**

  Run the preflight using the exact new qualification invocation ID, not a manually edited summary. Confirm that task IDs, config hash, evaluator hash, artifact hashes, and COM evidence match.

- [x] **Step 2: Require fail-closed behavior for any missing row**

  Run the preflight regression tests that mutate one task row and confirm the gate blocks without invoking the candidate provider.

- [x] **Step 3: Run the real preflight**

  Acceptance is `status=ready`, `rsi_started=false` before the experiment runner is explicitly invoked, and no candidate process is started during preflight.

### Task 5: Start controlled RSI only after the gate is ready

**Files:**
- Read: `project_artifacts/phase3_experiments/configs/general_office_rsi.json`
- Read: `project_artifacts/phase3_experiments/scripts/run_workagent_rsi.py`
- Create: new RSI result directory under `project_artifacts/results/experiments/`
- Modify: `project_artifacts/execution_log.md`

**Interfaces:**
- Consumes: qualified baseline, frozen develop/regression/hidden/OOD task splits, candidate provider and evaluator contracts.
- Produces: baseline/candidate records, per-task outcomes, diagnosis, promotion decision, rollback evidence, and a human-readable report.

- [x] **Step 1: Run baseline and candidate only through the guarded runner**

  Do not call the candidate generator directly. The runner must persist launch markers before process start, keep hidden/OOD tasks isolated, and stop on provider unavailable/timeout without assigning a score.

- [x] **Step 2: Require candidate promotion conditions**

  Promote only if develop improves, regression has no task loss, hidden/OOD remain within the configured thresholds, artifact/skill safety checks pass, and cost/timeout limits pass. Otherwise retain the baseline and record rollback/rejection.

- [x] **Step 3: Analyze and report**

  Generate the machine-readable summary and a human-readable report under one result directory. Clearly label project-generated pilot evidence separately from any external benchmark claim.

### Verification checklist before declaring the gate open

- [x] `check_office_capabilities.py` reports all three COM applications available.
- [x] One real `excel-create` task completes end to end.
- [x] The frozen six-task run is `6/6`, with no failure or unavailable rows.
- [x] Every artifact passes library-level evaluation and COM reopen.
- [x] Input source hashes are unchanged.
- [x] RSI preflight is `ready` and candidate launch has not happened before explicit start.
- [x] Full pytest, `compileall`, and `git diff --check` pass.
- [x] `Agent.md` and `project_artifacts/execution_log.md` describe the actual evidence without overstating it.
