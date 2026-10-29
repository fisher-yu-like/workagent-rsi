# T26 balanced development materials

On 2026-10-26 the user requested similar quantities of Excel, Word and PowerPoint material. The active candidate cohort contains24 base tasks in each domain,72 total. It selects existing spreadsheet inputs and adds external Word editing and editable diagram tasks. The larger source caches remain available; they are not all part of this cohort.

| Domain | Selected base tasks | Native instances | Source and task scope |
|---|---:|---:|---|
| Excel |24|24|Pinned SpreadsheetBench2 workbook editing tasks|
| Word |24|24|Pinned nberk/llm-docx-editing fixture editing tasks|
| PowerPoint |24|24|Pinned Einsia/PPTBench scientific diagram reconstruction tasks|

The sources have different task scopes. These quantities do not establish broad business-document coverage or a comparison of general ability across formats. In particular, the PowerPoint inputs are source figure PDFs and reference PNGs; the required output is an editable PPTX. This intake generates no new finished Office deliverables.

## Current files

- `project_artifacts/phase3_experiments/configs/benchmark_sources_v2_supplement.json` pins the new sources, permissions and authorship evidence.
- `project_artifacts/phase3_experiments/configs/benchmark_balanced_cohort_v1.json` records the selection rule and development scope.
- `project_artifacts/results/hardening-v2/T26-balanced/20261026/cohort-v2/evaluator-only/task-manifest.json` is the active private candidate manifest.
- `project_artifacts/results/hardening-v2/T26-balanced/20261026/cohort-v2/execution-views/` contains72 separate input-only task views.
- `project_artifacts/results/hardening-v2/T26-balanced/20261026/cohort-v2/task-index.csv` lists task instructions and local input-view paths.
- `project_artifacts/formal_study/hardening_t26_balanced_materials.json` is the current delivery receipt.

## Source admission

The Word source has50 tasks over31 referenced DOCX files. Its pinned fixture generator sources establish that these are project-authored benchmark fixtures under the repository's MIT license. They are not claimed to be private enterprise documents. Source definitions are parsed as literal data; no downloaded TypeScript or generator is executed. Expected strings and source checks remain in the private manifest.

The PPT source provides a version-specific license audit. Only CC BY, CC BY-SA or CC0 source versions with an affirmative reuse grant are eligible. The selected tasks need no external raster resources. Each original figure PDF must match the upstream SHA-256 before rendering. Reference PNGs use the upstream PyMuPDF1.28.0 alpha compositing and dimension-bound pixel hash; all24 match frozen upstream reference pixels. Attribution and any ShareAlike obligation remain with each source.

Two predefined PPT candidates were excluded for input availability: one did not yield the hash-bound figure, and one exceeded the archive size/time bound. No model outcomes or quality scores affected selection. Initial render/hash-check implementation differences were corrected offline; the initial pool and cohort remain historical, and `cohort-v2` is the active delivery.

GDPval was not admitted because its pinned dataset card/root did not supply an explicit data license. PresentBench remains a candidate pending permission review for individual background materials. Neither contributes tasks to this delivery.

## Family isolation and limits

Selection includes the old inventory when computing connected source groups. Any group connected to a T28 calibration task is excluded first. All173 reserved task records remain excluded, including transitive links. The selected72 tasks come from72 different connected groups under the declared source-family and file-hash rules. A source group's other tasks cannot independently fill missing slots.

Each domain has8 develop,8 regression,4 promotion-validation and4 OOD-transfer candidates. All are inspected public development materials. The extra regression allocation does not substitute for final evaluation. There are zero final-test cases and no untouched-final claim. OOD is a family holdout designation, not evidence of distribution-shift performance.

The original total of72 base tasks is reached, but the original216-instance requirement is not: there is one published input instance per selected task. Copies, renamed files and fabricated variants do not fill that gap. A protected untouched final corpus and a separate evaluator principal remain necessary for full T26 acceptance.

## Reproduction and validation

The preparation command uses a new pool and output directory. Discovery snapshots must retain the pinned source identities and accompanying license evidence.

```powershell
& .venv/Scripts/python.exe project_artifacts/phase3_experiments/scripts/prepare_balanced_office_materials.py --discovery <pinned-source-discovery> --pool <new-local-pool> --output <new-cohort> --previous <reserved-task-manifest.json>
```

The existing-pool finalization mode, `--finalize-existing-pool`, performs no new downloads or model calls. It verifies the saved PDF sources against their input hashes, renders hash-bound references and writes a new cohort. Prior evidence is preserved.

Actual validation checked120 exported input files, reopened24 XLSX and24 DOCX files, verified24 frozen reference images, checked family isolation against all173 calibration records and reverified the unchanged32-case T28 review-pack hash. Downloaded source archives total144,141,555 bytes and stay on Windows. No server operation or model request occurred.

Source links: [Word benchmark](https://github.com/nberk/llm-docx-editing), [PPTBench data licensing](https://github.com/Einsia/PPTBench/blob/main/DATA_LICENSE.md), [PPTBench source audit](https://github.com/Einsia/PPTBench/blob/main/SOURCE_LICENSE_AUDIT.md).
