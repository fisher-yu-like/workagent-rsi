# Benchmark task intake for T26 to T28

The source order is SpreadsheetBench 2, Workspace-Bench-Lite, then SpreadsheetBench 1. The source versions, license evidence, file sizes and upstream content identities are in `project_artifacts/phase3_experiments/configs/benchmark_sources_v1.json`. Original files stay in the ignored local results cache. They are not committed or uploaded as a full collection to the 4 GB server.

The admitted development inventory contains 1,333 task records. SpreadsheetBench 2 supplies 321 tasks and 321 native input cases. SpreadsheetBench 1 supplies 912 tasks and 2,726 native input cases in the pinned archive. Its README advertises 2,729 cases, so the observed archive count is retained rather than replaced with the advertised count. There are 905 tasks with three variants, four with two, and three with one.

Workspace-Bench-Lite supplies the list of 100 task IDs. Its dataset card has no license field. The full Workspace-Bench dataset explicitly declares Apache-2.0. All 100 corresponding task instructions, output lists and rubrics match the licensed full release. This adapter uses the full release's annotations and assets at those IDs. Eighty tasks have a different input list or dependency graph from Lite; that difference is recorded. The downloaded 32 Office task input bundles contain 208 files and 62,449,760 bytes. Sixty-eight other task records have no admitted Office execution bundle in this adapter.

This is an adapted subset. Supplying referenced task files changes the workspace search problem, because the full noisy workspaces are absent. These runs cannot be reported as native Workspace-Bench-Lite leaderboard results. The raw English workspace ZIP is about 18.7 GB and is not downloaded.

## Data preparation

Install optional native scorer dependencies in the local project environment with `python -m pip install -e ".[benchmark]"`. The observed local versions are NumPy 2.5.4 and tqdm 4.70.1. No new packages are installed on the server.

```powershell
& .venv/Scripts/python.exe project_artifacts/phase3_experiments/scripts/prepare_benchmark_corpus.py --cache <new-or-verified-local-cache> --output <new-corpus-directory> --fetch-workspace
```

The downloader checks the pinned SHA-256 or Git blob identity, streams within declared size and time limits, and rejects changed cached files. Archive extraction rejects traversal, links, duplicate paths and excessive expansion. Existing extracted files are verified against the extraction receipt before reuse.

The task manifest contains native evaluation targets and belongs to the evaluator. `export_execution_inputs` creates a separate execution view containing only the current instruction and hash-verified input files. It never exports reference workbooks or hidden rubrics. Workspace inputs retain their declared filenames; a metadata filename collision is rejected.

## Source grouping and the final corpus

The adapter joins tasks through source-family identity and shared input or reference content, including transitive connections. Workspace personas are kept together conservatively. Source groups are assigned before any variant export. Native variants remain together, and missing variants are never replaced with copied or renamed files.

The inventory and source metadata have been inspected. Its development splits therefore have no untouched-final claim. The original T26 requirement remains 72 base tasks, 216 distinct input instances, balanced per domain, with an evaluator-side final corpus. The selected benchmarks do not satisfy the Word/PPT family and three-variant requirements. T26 remains blocked for that acceptance level. Existing candidate-container mount denial does not establish a separate evaluator account.

The T28 preparation command reserves whole connected groups before outputs are generated:

```powershell
& .venv/Scripts/python.exe project_artifacts/phase3_experiments/scripts/prepare_benchmark_review_run.py --manifest <corpus/evaluator-only/task-manifest.json> --output <new-planned-run-directory>
```

The first planned cohort has ten Excel, seven Word and three PowerPoint tasks. It uses ten SpreadsheetBench 2 tasks and ten Workspace tasks. It spans nine connected source groups. All 173 task records in those groups move to `human_calibration`; they cannot remain in development, promotion or OOD evaluation. The active manifest is the new `evaluator-only/reserved-task-manifest.json`, accompanied by `reserved-split-quality-report.json`. The earlier corpus manifest is a historical pre-reservation snapshot.

Every job has a fixed input manifest, a bounded input preview and a request hash. Selection uses declared format support, a four MB input limit, the source priority, and a fixed ordering hash. It does not use model success or evaluator scores. The twenty planned files are not twenty independent source families.

## Native scoring and T27

The pinned native scorer identities are in `benchmark_native_scorers_v1.json`. The upstream programs remain unmodified in the local cache and are not vendored into this repository. `benchmark_scoring.score_spreadsheet` requires isolated recalculation evidence for the input, reference and output. All three must use the same engine configuration, and source/output hashes must match. The original input and reference must belong to the same frozen native variant. A missing engine, stale cache or unavailable dependency leaves the score null.

SpreadsheetBench 2 visualization scoring needs its native Windows Excel/WPS COM and VLM workflow. The development numeric scorer returns unavailable for that category. Native cell checks do not establish complete artifact quality. The server has LibreOffice 7.4.7, so these are recorded integration checks, not a claim of matching every published environment requirement.

Two actual benchmark input controls were recalculated on the server and rejected by their native scorers. The SpreadsheetBench 2 control preserved 251 regression cells and missed 37 required modifications. These results qualify the connection to the scorer and the isolated calculation worker. An unmodified input is not a model output, and these two controls do not measure scoring accuracy.

The original T27 development calibration remains separate. Its new run again observed 45 PASS, 28 FAIL and 17 INCOMPLETE outcomes on the 90 controlled Office artifacts. It observed zero false accepts among 28 determinate defect decisions and zero false rejects among 45 accepted correct/equivalent decisions. Fifteen evidence gaps and two visual defects remain incomplete. These counts do not establish independent population accuracy.

## T28 execution and human review

```powershell
& .venv/Scripts/python.exe project_artifacts/phase3_experiments/scripts/run_benchmark_review_jobs.py --plan <planned-run/run-plan.json> --live-policy <new-approved-policy.json> --sandbox-policy <qualified-Apptainer-policy.json> --output <new-actual-run-directory>
```

The runner refuses disabled policies. The proposal permits at most twenty gpt-6.1-sol CLI requests, forty server execution/render operations, and 3,600 cumulative model-request seconds. The CLI returns Python as data with tools disabled. Only the Apptainer worker executes that Python. No failed job receives an automatic retry. A generated program is syntax-checked locally but is never executed on Windows. The 4,096 output-token limit is a prompt instruction, because this CLI cannot enforce a server token cap.

An actual output is admitted only after remote execution and a successful Office-library reopen. Its source references and file hashes are retained in `natural-manifest.json`. Missing outputs remain missing. Reference answers cannot fill the twenty-output requirement. A new run directory is required so an interrupted run cannot be replayed automatically.

After at least twenty outputs exist, use `prepare_human_calibration.py --natural-manifest <actual-run/natural-manifest.json>` with the existing standards manifest. Reuse the twelve standards' already verified render pages, and reserve the remaining server operations for the twenty natural outputs. Rendering all thirty-two files again would exceed this proposal's forty operations after generation.

The user must submit actual labels. Judge results stay hidden until labels are fixed. Judge calls require a separate bounded approval. A changed rubric requires a new evaluator identity and a rerun of the whole comparable cohort. At this delivery there are twenty prepared jobs, zero new model calls, zero natural model outputs and zero submitted human labels. The earlier instruction to defer materials was superseded by the user's request to prepare these benchmarks.

## Validation

Use `run_hardening_checks.py <label> --profile benchmark-intake` for the focused checks. This delivery ran 41 checks, with zero failures or skips. The previous full run of 717 checks is historical evidence; it is not reported as a new full run.

Source pages: [SpreadsheetBench 2 data](https://huggingface.co/datasets/KAKA22/SpreadsheetBench-v2), [Workspace full data](https://huggingface.co/datasets/Workspace-Bench/Workspace-Bench), [Workspace Lite data](https://huggingface.co/datasets/Workspace-Bench/Workspace-Bench-Lite), and [SpreadsheetBench 1](https://github.com/RUCKBReasoning/SpreadsheetBench).
