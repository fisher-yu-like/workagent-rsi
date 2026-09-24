# Phase 3 Experiments

## Current state

The Phase 3 data layer, local Office qualification, closed-loop RSI infrastructure and E01-E12 pilot executions are complete.

- Dataset: 30 project-generated pilot tasks, with 25 public and 5 protected records.
- Data quality: 14 checks passed.
- Local mock qualification: 25/25 tasks succeeded with the text evaluator.
- Local Office qualification: 25/25 tasks generated genuine DOCX/XLSX/PPTX files, passed format-aware reopening, and passed read-only Word/Excel/PowerPoint 16.0 COM open/close checks.
- Candidate provider: Codex CLI 0.144.2 with local Ollama qwen2.5:7b in isolated workspaces.
- E01-E12: twelve latest pilot invocations completed with immutable contracts and evidence.

## Claim boundary

B0 runs qualify the local Harness, artifact generation, evaluator and Office runtime. E01-E12 are controlled pilot RSI executions over the project-generated 30-task fixture. They are not external WorkAgent results, model-weight training, or powered main-study evidence. E07 uses automated cross-evaluation and makes no human-label claim.

## Remaining research work

A main study still requires at least 90 independently sourced or template-separated tasks, more seeds, richer formula/layout/visual evaluators, a second executor/model, and independent visual calibration.
