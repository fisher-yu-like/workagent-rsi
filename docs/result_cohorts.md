# Comparable experiment analysis (T09)

`analyze_cohorts(root)` reads results without modifying historical evidence.
The compatible `analyze_formal.py` CLI delegates to it:

```powershell
& .\.venv\Scripts\python.exe -X utf8 project_artifacts/phase3_experiments/scripts/analyze_formal.py --help
& .\.venv\Scripts\python.exe -X utf8 project_artifacts/phase3_experiments/scripts/analyze_formal.py <results-root> --output <new-analysis.json>
```

Numbers are grouped by mode, dataset/split identity, evaluator, acceptance
specifications, model configuration, experiment arm and budget policy. Different
keys never share a mean. Each cohort reports sample count, task observations,
per-metric denominators and the exact source run/attempt/identity/result refs.
The compatibility `numeric_means` field is populated only for one cohort without
blocking exclusions. `claims_allowed` is cohort-scoped; a mixed directory never
inherits permission from one formal summary.

## Bound evidence format

An aggregate `summary.json` retains `mode` and `experiments`. Each experiment
record supplies `run_id`, positive integer `attempt_id`, status, numeric metrics,
and `identity_ref` / `result_ref`. File refs are `{ "path": "relative/file.json",
"sha256": "..." }`, relative to that summary directory. Links, traversal,
hardlinks, changed hashes and evidence files over 16 MiB are rejected. These
metadata/source bounds fail explicitly rather than partially reading evidence.

The identity file has schema_version `cohort-identity-v1` and exactly:

- mode: pilot or formal;
- dataset_hash: canonical JSON hash of split_hashes;
- split_hashes: nonempty split-name to canonical task-record-list hash map;
- evaluator_hash: immutable evaluator/configuration identity;
- acceptance_hashes: nonempty task-ID to acceptance-definition hash map;
- model_config: explicit provider/model configuration, without credentials;
- experiment_arm: the actual arm, distinct for incomparable policies;
- budget_policy: actual versioned resource/edit budget configuration.

The result file binds the same run_id, attempt_id, status and canonical identity
hash. It includes a unique provenance evidence_id, metrics, and task_results
with task_id and metrics. Completed results must cover every declared acceptance
task exactly once. This v1 format admits numeric task-mean metrics: per-task
metric keys must agree, and their mean must match the recorded run value.
Other aggregation conventions need an explicitly versioned format; they are
not silently interpreted as task means. Bool, NaN, Infinity and malformed or
unverifiable identities never enter numeric aggregates.

Historical summaries missing these identities/references remain visible in
observed status counts and exclusion reasons. They are not silently upgraded
by inferring a dataset/model/budget from a directory name or reused experiment
label. Their original files remain untouched. Producers must record actual
identities and observations for new analysis; do not backfill invented values.

## Duplicates and retries

The highest declared attempt wins, even when it failed or its evidence is
invalid. Older success is never resurrected to improve the mean. Identical
run+attempt copies count once. Conflicting same-attempt records are excluded;
verified retry identities must agree. Reused evidence across different logical
runs is excluded. Each exclusion carries its source and reason. Raw observed
status counts are distinct from the selected numeric sample count.

## Formal claim boundary

An eligible formal cohort additionally needs external-admitted scope and a
hash-bound `cohort-admission-v1` receipt referenced by `admission_ref`. It binds
the cohort identity/dataset and includes source_manifest, quality_report and
split refs (all relative to the summary directory). The analyzer verifies ready
source admission, the selected source's recorded license/checksum/download
status, matching passed quality admission, actual split hashes and complete,
nonoverlapping task coverage. A ready/external-benchmark boolean alone cannot
authorize a claim. All included observations need valid admission and the same
metric coverage. Pilot and unverified cohorts keep claims_allowed=false.

This checks the recorded evidence and its consistency. Independent source
admission, evaluator correctness, reviewed requirements and authenticity of
measurements remain separate responsibilities. Authored unit fixtures exercise
these gates; they are not real external benchmark results.

## Paired reference evaluation

`paired_reference_evaluation(new_destination, tasks=..., parent_package=...,
candidate_package=..., evaluator=..., evaluator_hash=..., source_runs=...)`
invokes one trusted evaluator on identical tasks and both versions. It creates
an exclusive `reference_eval_run`, saving inputs, source snapshots, per-task
pairs, deltas and hashes. Existing destinations fail instead of overwriting
history. Evaluator failures/non-finite observations persist as failed reference
runs. The helper grants no formal claim or permission to make live model calls;
the caller must use an authorized evaluator/environment. T09 tests use only
authored local callbacks.
