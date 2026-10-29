# Input behavior qualification

`TaskObservation` separates actual input hashes and inspected structure from the agent-declared operations and verification plan. Requested changes come from the current public task instruction. Observations never include acceptance specifications, hidden answers or evaluator rules.

The optional native `inspect_office` tool accepts only the exact staged Office input named in the current manifest. A trusted inspection program runs through the configured T04 sandbox and returns actual worksheets/cells, paragraphs/tables or slide shapes. Its source hash, input hash, execution result and host-owned evidence are recorded. Failed sandbox capability does not execute the inspection on the host. Returned structure has bounded text and counts; truncation is partial, never full visibility. Clients can choose other valid inspection/execution plans, but absent evidence is recorded as not observed.

The Office adapter writes `provider_records/task-observation.json` after provider execution. Read evidence is checked against host-owned inspection files, their hashes and the current inputs. The native tool log and exact generation script snapshots remain separate. Observations do not by themselves prove that a program used every inspected field.

`run_behavior_probes(skill, probe_manifest, executor)` passes only the public task and public operation request to the executor. Independent expected values, locations, text, styles and counts remain with the verifier. It requires actual read records for supplied inputs, generation source and process traces, unchanged source files, correct artifacts and the expected response to changed inputs/requests. Changing task IDs alone must preserve semantic output. A single source hash may pass all variants; changed source hashes are not evidence of adaptation.

The project-generated T24 corpus has nine groups, three per domain, with 22 cases including three randomized-ID controls. Excel varies worksheet names, values/last rows, column positions and column counts. Word varies edit targets, paragraph counts/heading levels and table structure. PowerPoint varies requested page count, edit target and source page count with an authorized append.

Run the trusted local engineering qualification with:

```powershell
.venv\Scripts\python.exe project_artifacts/phase3_experiments/scripts/run_t24_behavior_probe.py --output-root <fresh-directory>
```

The local executor runs only the repository's fixed authored program and exact trusted inspectors. It evaluates no candidate skill text or generated model code. It records actual subprocess commands, exit codes, stdout/stderr, scripts, tool calls, inputs and real Office files. It is qualification_only and reports no live-model or sandbox qualification. Arbitrary injected executors have unknown model-call usage unless they supply a counter. There is no default executor or host fallback in production.

This corpus qualifies the observation and behavioral-verification plumbing and the authored dynamic implementation. It does not establish that the current model/champion generalizes, does not measure model accuracy, and does not replace fresh live T04/T31 qualification or later human/research evaluation. Formula recalculation, COM reopening and rendered layout are outside these literal-value/text/count oracles. Existing T13/T14 qualification remains separately scoped.
