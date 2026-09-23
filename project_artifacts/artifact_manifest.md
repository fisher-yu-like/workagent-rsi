# Artifact Manifest

| File | Phase | Type | Purpose | Validation | Real run data |
|---|---|---|---|---|---|
| `docs/literature_review.md` | 0 | Markdown | Two-paper evidence review and design mapping | File written; source links and local HTML paths checked | No |
| `docs/sources/rrsi-2609.24972.html` | 0 | HTML | Preserved arXiv source | Retrieved from arXiv | No |
| `docs/sources/genuine-rsi-2609.11873.html` | 0 | HTML | Preserved arXiv source | Retrieved from arXiv | No |
| `project_artifacts/phase1_harness/design/repository_audit.md` | 1A | Markdown | Repository audit | File written | No |
| `project_artifacts/phase1_harness/design/environment_inventory.md` | 1A | Markdown | Runtime inventory | File written | No |
| `project_artifacts/phase1_harness/design/harness_architecture.md` | 1A | Markdown | Component architecture | File written | No |
| `project_artifacts/phase1_harness/design/component_specifications.md` | 1A | Markdown | Component contracts | File written | No |
| `project_artifacts/phase1_harness/design/pipeline_design.md` | 1A | Markdown | Pipeline state/flows | File written | No |
| `project_artifacts/phase1_harness/design/interfaces.md` | 1A | Markdown/Python | Interfaces | File written | No |
| `project_artifacts/phase1_harness/design/test_and_acceptance_plan.md` | 1A | Markdown | Test and gate plan | File written | No |
| `project_artifacts/phase1_harness/design/implementation_backlog.md` | 1A | Markdown | Phase 1B backlog | File written | No |
| `project_artifacts/execution_plan.md` | 1A | Markdown | Three-phase status | File written | No |
| `project_artifacts/artifact_manifest.md` | 1A | Markdown | Artifact index | This file | No |
| `Agent.md` | 1A | Markdown | Agent operating contract | Pending in this baseline | No |
| `pyproject.toml` | 1B | TOML | Package and pytest configuration | Editable install completed with Python 3.12 | No |
| `src/workagent_rsi/` | 1B | Python | Harness contracts, stores, adapter, evaluator, orchestrator and CLI | 14 pytest tests pass | No |
| `tests/` | 1B | Python | Unit, integration and end-to-end tests | 14 pytest tests pass | No |
| `project_artifacts/phase1_harness/results/run_summary.json` | 1B | JSON | Mock run results | JSON parsed and evidence paths checked | Yes, local mock data |
| `project_artifacts/phase1_harness/results/run_summary.csv` | 1B | CSV | Tabular mock run results | Generated from same run records | Yes, local mock data |
| `project_artifacts/phase1_harness/reports/run_report.md` | 1B | Markdown | Mock Pipeline report | Linked to per-run JSON evidence | Yes, local mock data |
| `project_artifacts/phase1_harness/reports/Harness详细设计与运行报告.docx` | 1B | DOCX | Phase 1B design and mock run report | Reopened; rendered through Microsoft Word to one PDF page and visually inspected | Yes, local mock data |
| `project_artifacts/phase1_harness/reports/Harness与WorkAgent运行报告.pptx` | 1B | PPTX | Phase 1B presentation | Artifact Tool finalizer passed; six slides rendered and visually inspected | Yes, local mock data |
| `project_artifacts/phase1_harness/reports/Harness运行数据.xlsx` | 1B | XLSX | Seven-sheet run workbook | Artifact Tool formula scan passed; all sheets rendered and visually inspected | Yes, local mock data |
| `project_artifacts/phase2_rsi/design/research_canon.md` | 2 | Markdown | Evidence boundary and source-derived design constraints | Source claims separated from project decisions | No |
| `project_artifacts/phase2_rsi/design/evidence_table.md` | 2 | Markdown | Evidence-to-design traceability | Claim, source, implication and limitation fields checked | No |
| `project_artifacts/phase2_rsi/design/argument_map.md` | 2 | Markdown | Research questions, hypotheses and controls | Hypotheses map to risks and planned controls | No |
| `project_artifacts/phase2_rsi/design/section_contracts.md` | 2 | Markdown | Phase 2 section acceptance contracts | Prohibited result claims and acceptance checks recorded | No |
| `project_artifacts/phase2_rsi/design/terminology_ledger.md` | 2 | Markdown | Stable RSI terminology | Terms and operational meanings reviewed | No |
| `project_artifacts/phase2_rsi/design/rsi_architecture.md` | 2 | Markdown | RSI scope, control plane and safety architecture | Architecture boundaries and promotion invariants reviewed | No |
| `project_artifacts/phase2_rsi/design/rsi_component_design.md` | 2 | Markdown | Component responsibilities and contracts | Inputs, outputs and safety constraints documented | No |
| `project_artifacts/phase2_rsi/design/rsi_data_flow.md` | 2 | Markdown | Evidence and version data flow | Provenance, split isolation and leakage controls documented | No |
| `project_artifacts/phase2_rsi/design/rsi_training_flow.md` | 2 | Markdown | Pilot-to-transfer optimization flow | Stages, gates and stop conditions documented | No |
| `project_artifacts/phase2_rsi/training_plan/training_plan.md` | 2 | Markdown | Executable training and evaluation protocol | Baselines, splits, metrics, statistics and Go/No-Go rules reviewed | No |
| `project_artifacts/phase2_rsi/training_plan/experiment_matrix.csv` | 2 | CSV | Machine-readable experiment plan | Twelve planned rows; priorities count to 7 P0, 4 P1 and 1 P2 | No |
| `project_artifacts/phase2_rsi/training_plan/experiment_matrix.xlsx` | 2 | XLSX | Experiment summary and detailed matrix | Formula scan found no errors; two sheets rendered, inspected and reopened | No |
| `project_artifacts/phase2_rsi/training_plan/resource_budget.csv` | 2 | CSV | Machine-readable resource assumptions | Quantities and authorization notes reviewed | No |
| `project_artifacts/phase2_rsi/training_plan/resource_budget.xlsx` | 2 | XLSX | Editable resource budget | Formula scan found no errors; sheet rendered, inspected and reopened | No |
| `project_artifacts/phase2_rsi/training_plan/build_phase2_artifacts.mjs` | 2 | JavaScript | Reproducible PPTX/XLSX builder | Executed with bundled Artifact Tool; compile inputs and finalizer passed | No |
| `project_artifacts/phase2_rsi/training_plan/generate_phase2_docx.py` | 2 | Python | Reproducible DOCX builder | Python 3.12 compile passed; output reopened and rendered | No |
| `project_artifacts/phase2_rsi/reports/RSI整体框架与训练计划.docx` | 2 | DOCX | RSI architecture and training-plan report | Reopened; rendered through Microsoft Word to two PDF pages and visually inspected | No |
| `project_artifacts/phase2_rsi/reports/RSI整体框架与训练计划.pptx` | 2 | PPTX | Phase 2 architecture and plan presentation | Artifact Tool finalizer passed; nine slides rendered, inspected and reopened | No |
| `project_artifacts/phase2_rsi/evidence/validation_summary.md` | 2 | Markdown | Phase 2 validation record and claim boundary | Commands, hashes, failures and final checks recorded | No |
| `project_artifacts/phase2_rsi/evidence/pptx_validation.json` | 2 | JSON | Presentation finalizer receipt | Package, layout, font and first-party import checks passed | No |
| `project_artifacts/phase2_rsi/evidence/experiment_matrix_formula_scan.ndjson` | 2 | NDJSON | Experiment workbook error scan | Zero error-cell matches | No |
| `project_artifacts/phase2_rsi/evidence/resource_budget_formula_scan.ndjson` | 2 | NDJSON | Resource workbook error scan | Zero error-cell matches | No |
| `project_artifacts/phase2_rsi/evidence/renders/pptx/` | 2 | PNG set (9 files) | Nine-slide visual evidence | All nine images inspected at full size | No |
| `project_artifacts/phase2_rsi/evidence/renders/docx/` | 2 | PNG set (2 files) | Two-page Word render evidence | Both final pages inspected at full size | No |
| `project_artifacts/phase2_rsi/evidence/renders/experiment-matrix/` | 2 | PNG set (2 files) | Experiment workbook visual evidence | Summary and detail sheets inspected | No |
| `project_artifacts/phase2_rsi/evidence/renders/resource-budget/` | 2 | PNG set (1 file) | Resource workbook visual evidence | Resource sheet inspected | No |
| `project_artifacts/phase3_experiments/data/dataset_catalog.md` | 3 | Markdown | Dataset source, license, fields and leakage policy | Scope explicitly marked project-generated; external benchmark claims prohibited | No |
| `project_artifacts/phase3_experiments/data/README.md` | 3 | Markdown | Data-layer reproducibility commands | Generator and quality-check commands documented | No |
| `project_artifacts/phase3_experiments/data/generate_dataset.py` | 3 | Python | Deterministic pilot task generator | Python 3.12 compile passed; fixed seed and provenance output | No |
| `project_artifacts/phase3_experiments/data/quality_check.py` | 3 | Python | Dataset schema, split and leakage gate | 14 checks passed; non-zero on drift or leakage | No |
| `project_artifacts/phase3_experiments/data/raw/tasks_all.jsonl` | 3 | JSONL | Immutable generated task source layer | 30 records; hash recorded in provenance | No |
| `project_artifacts/phase3_experiments/data/processed/public_tasks.jsonl` | 3 | JSONL | Candidate-facing public task layer | 25 records; excludes hidden tasks | No |
| `project_artifacts/phase3_experiments/data/protected/hidden_tasks.jsonl` | 3 | JSONL | Local protected qualification layer | 5 records; isolated from public export | No |
| `project_artifacts/phase3_experiments/data/splits/` | 3 | JSONL set | Split-specific task manifests | Evolve/develop/regression/OOD counts checked | No |
| `project_artifacts/phase3_experiments/data/provenance.json` | 3 | JSON | Dataset hashes, environment and generation record | Hashes and counts cross-checked by quality gate | No |
| `project_artifacts/phase3_experiments/data/quality_report.json` | 3 | JSON | Dataset quality and leakage report | Status `pass`; 14 checks passed | No |
| `project_artifacts/phase3_experiments/scripts/run_b0_qualification.py` | 3 | Python | Local mock B0 qualification runner | 25 public tasks executed through existing Harness | Yes, local mock data |
| `project_artifacts/phase3_experiments/results/b0_qualification/` | 3 | JSON/CSV/SQLite set | Per-task traces, artifacts and B0 summary | 25 succeeded, 0 failed; scope limitation recorded | Yes, local mock data |
| `project_artifacts/phase3_experiments/results/b0_qualification/attempt_001_failure.json` | 3 | JSON | First B0 contract-mapping failure | Failure preserved with resolution | Yes, local run evidence |

Phase 1B local mock runs are real executions of the repository code. They are not executions of an external WorkAgent provider or real Office task adapter.

Phase 2 artifacts are designs and plans. They contain no executed training, dataset experiment or benchmark score.
