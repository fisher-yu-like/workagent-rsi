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

Phase 1B local mock runs are real executions of the repository code. They are not executions of an external WorkAgent provider or real Office task adapter.
