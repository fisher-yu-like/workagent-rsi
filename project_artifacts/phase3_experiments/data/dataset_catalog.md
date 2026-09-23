# Phase 3 Dataset Catalog

## Scope

This first Phase 3 task set is a **project-generated pilot fixture** for validating task routing, trace capture, split isolation and evaluator plumbing. It is not an external benchmark, does not carry an external dataset license, and does not support general Office-agent performance claims.

The fixture contains 30 tasks balanced across Excel, Word and PowerPoint. The split plan is fixed before execution:

| Split | Count | Purpose |
|---|---:|---|
| evolve | 12 | Candidate proposal and controlled skill evolution |
| develop | 6 | Development selection |
| regression | 4 | Protected non-regression checks |
| hidden | 5 | Protected local-only qualification tasks |
| ood_transfer | 3 | Transfer and held-out template-family checks |

## Source and license

| Field | Value |
|---|---|
| Source kind | `project-generated` |
| Generator | `data/generate_dataset.py` |
| Version | `synthetic-office-taskset-v0.1.0` |
| Seed | `20260923` |
| License | Internal generated fixture; no external benchmark license claimed |
| External download | None |
| External citation | None |

The source record for every task points to the generator and records the dataset version, seed and template family. A later externally sourced dataset must add an official URL, publisher, version, license text, retrieval timestamp and checksum before it can enter a formal experiment.

## Fields

`task_id`, `domain`, `difficulty`, `split`, `template_family`, `instruction`, `input_files`, `expected_constraints`, `risk_level`, `hidden_test`, `source`, `dataset_version` and `seed` are required. `expected_constraints.required_text` is a deterministic marker used only by the current text evaluator qualification path.

## Leakage controls and limitations

- `processed/public_tasks.jsonl` excludes all hidden tasks.
- `protected/hidden_tasks.jsonl` is stored separately and is never passed to the candidate-facing public export.
- Instructions are unique and task IDs are unique. The quality gate rejects duplicate instructions and split-count drift.
- The repository is not a cryptographic secret store. The protected file is a local qualification boundary, not evidence of a secure hidden benchmark.
- The current mock adapter emits text rather than genuine Office artifacts. Any baseline using it is labelled `mock_harness_qualification` and cannot be promoted to an Office capability result.
