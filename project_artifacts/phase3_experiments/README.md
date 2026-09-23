# Phase 3 Experiments

## Current state

The Phase 3 data layer and local Office provider qualification are complete.

- Dataset: 30 project-generated pilot tasks, with 25 public and 5 protected records.
- Data quality: 14 checks passed.
- Local mock qualification: 25/25 tasks succeeded with the text evaluator.
- Local Office qualification: 25/25 tasks generated genuine DOCX/XLSX/PPTX files, passed format-aware reopening, and passed read-only Word/Excel/PowerPoint 16.0 COM open/close checks.

## Claim boundary

These runs qualify the local Harness, artifact generation, format evaluator and Office runtime. They are not external WorkAgent runs and are not formal RSI experiment results. The project has not run E01-E12, hidden evaluation, candidate promotion or model training.

## Remaining gate

Formal experiments require a configured candidate generator or external WorkAgent provider. Until that provider is available, the repository preserves the local B0 qualification evidence and keeps formal experiments pending.
