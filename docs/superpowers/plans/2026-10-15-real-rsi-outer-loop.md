# Real RSI Outer Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a real non-Ollama CandidatePatch and execute one auditable RSI outer-loop round over nonempty Excel, Word, PowerPoint splits.

**Architecture:** Add a bounded OpenAI-compatible candidate provider that returns validated `CandidatePatch` JSON and records request/response evidence. Reuse the existing `WorkAgentExperimentRunner`, `RSILoop`, evaluator, verifier, and promotion gates without changing their protected logic. Use one task per required split for the first live round, with a single non-Ollama model and preserved run artifacts.

**Tech Stack:** Python 3.12, Pydantic contracts, `urllib.request`, existing WorkAgent API provider, artifact-v1 evaluator/verifier.

**Spec:** `project_artifacts/formal_study/next_steps_20261011.md`

## Global Constraints

- Do not use Ollama.
- Candidate edits may target only `skill.json` and only allowlisted WorkAgent skill fields.
- Hidden and OOD task content must not be included in develop feedback.
- Preserve every failed and successful run directory.
- Do not change evaluator, verifier, Harness, or protected split logic for the live run.

---

### Task 1: Add the real candidate provider

**Files:**
- Modify: `src/workagent_rsi/candidate_provider.py`
- Test: `tests/test_candidate_provider.py`

**Interfaces:**
- Add `OpenAIChatCandidateProvider.generate_with_feedback(workspace, feedback, parent_version, edit_budget, record_root)`.
- Return `(CandidatePatch | None, ProviderRecord)`.
- Record `candidate.json`, request/response JSON, provider stderr, and `provider_record.json`.

- [ ] Add a failing unit test for model identity, bounded prompt, and JSON response parsing.
- [ ] Implement the provider with API-key lookup, bounded retries for HTTP 429, strict `CandidatePatch` validation, and workspace hashing.
- [ ] Run the focused provider tests.

### Task 2: Create the live four-split fixture

**Files:**
- Create: `project_artifacts/formal_study/run_live_rsi_outer_loop.py`

**Interfaces:**
- Build nonempty `develop`, `regression`, `hidden`, and `ood_transfer` `TaskSpec` lists.
- Use the existing `WorkAgentExperimentRunner` and artifact-v1 evaluator.
- Use `openai-chat:deepseek-v4-flash` for both WorkAgent and candidate generation.

- [ ] Define one task per split with distinct task IDs and constraints.
- [ ] Freeze split hashes through the runner contract.
- [ ] Execute one outer-loop round and print a compact summary.

### Task 3: Validate and document the real round

**Files:**
- Create: `results/rsi-live-api-20261015/human_readable_rsi_report_zh.md`

- [ ] Read baseline, candidate, verifier, promotion, provider, and checkpoint records.
- [ ] Report accepted/rejected/incomplete status with exact evidence paths.
- [ ] Explicitly report any API failures, COM-disabled status, and semantic/visual scope limits.
- [ ] Run focused tests, `compileall`, and `git diff --check`.
