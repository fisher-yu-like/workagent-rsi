# Development calibration and human review

The actual six-case follow-up was received on2026-10-26:3FAIL/3INCOMPLETE,all6 revised from the original labels. Exact bytes and separate provenance are under `project_artifacts/formal_study/human_review/20261026/adjudication-v1/`. Two interpretations still differ from the authored standard reference. Neither side is overwritten. These are6 nonblind revisions of existing cases,not6 new independent blind labels. `human_adjudication.intake_adjudication` validates parent submission/request/rubric/asset hashes,explicit requirements checks,unique complete case IDs and actual external provenance before writing. The original32 labels remain intact;full-cohort reference qualification is still pending.

Latest offline preparation: [the six-case follow-up page and user instructions](operations/next-human-checkpoint-20261026.md) are ready. Judge v2 includes the original task in visual review and separates content from rendered placement obligations. Its24 requests require new manifest-bound approval; no v2 calls were made. Follow-up exports are explicitly nonblind adjudication and cannot enter the original blind-label intake.

Update2026-10-26: the user supplied32 actual labels (29PASS,2FAIL,1PARTIAL) and disclosed quick visual review and uncertain accuracy. The original bytes are frozen in `results/hardening-v2/T28-human-intake/20261026/submission-v1/`. They are provisional references, not verified truth. See [the targeted follow-up](operations/human-review-follow-up-20261026.md) for repeated-task explanations and six controlled-standard differences. Earlier statements below about no submitted labels describe the historical delivery.

Intake now records `--review-depth quick_visual --reviewer-uncertain` and an optional `--review-note`. Only an explicit requirements-checked, non-uncertain receipt passes the reference gate. Provisional labels retain raw disagreement counts, but `critical_false_accepts` stays null: a human FAIL paired with a judge PASS is an unresolved difference, not proof of evaluator error. Revisions after seeing diagnostic results are adjudication records, not independent blind labels.

The newly approved12-standard pilot attempted6 of24 requests with gpt-6.1-sol and zero tools. Five channel decisions returned; request6 failed with HTTP429 and execution stopped without retry. Only2 cases have both channels returned, so neither full32-case agreement nor T28 qualification is established. The remaining18 requests were not issued. See `results/hardening-v2/T28-judge-pilot/20261026/actual-v1/diagnostic-summary.json` for recorded usage and scope.

T27 runs the production SharedAssessment, ArtifactEvaluator and ArtifactVerifier
against the90 T25 materials. Its compiler reads task instructions and frozen
input documents. It does not read labels or outputs to choose expected results.
Explicitly authorized alternatives are checked separately: any PASS accepts,
all FAIL rejects, otherwise the result stays INCOMPLETE. These are observations
of declared checks. No agent-generated human-review provenance is supplied to
claim reviewed whole-task admission.

PARTIAL is not accepted. Gap cases are excluded from artifact-error denominators.
Unresolved artifact cases stay in the overall denominator and are reported
separately; conditional error rates use observed decisions only. Location results
use the known defect target, not every location in the task. Wilson intervals
are descriptive case counts; related cases are not independent population
samples. There is no general accuracy claim.

T28 first prepares12 standards cases, four per domain, covering correct,
defective, authorized equivalent and unresolved requirements. File IDs are
randomized, and truth and source-family mappings stay outside the review pack.
The user sees task instructions, inputs, Office files and actual isolated
LibreOffice/Poppler render pages. The offline HTML page has empty label choices
and exports a JSON file only after the reviewer fills them. It makes no network
requests and never automatically submits a label.

The user has agreed to review these cases. A downloaded file must actually be
provided by the reviewer before intake. The controller retains its exact bytes,
computes a submission hash, and records the user/file reference and receipt time.
HumanLabel binds each decision to that receipt, reviewer, case and rubric hash.
A model name, a source_kind string or an agent-signed JSON record alone cannot
establish human provenance. The trusted controller must observe the external
submission; this code is not an identity-authentication service.

```powershell
& .venv/Scripts/python.exe -m workagent_rsi.human_calibration intake --submission <actual-reviewer-file.json> --review-manifest <blind-review-pack/review-manifest.json> --output <new-private-intake-directory> --reviewer-id <actual-reviewer> --evidence-ref <actual-user-message-or-file-reference>
```

Judge decisions use opaque case IDs, the frozen rubric hash and an evaluator
identity. Human labels must be fixed before judge results are revealed. Changed
rubrics require a new identity and rerunning the entire comparable cohort.
Comparison rejects duplicate cases, mixed identities, missing provenance and
rubric mismatches. It reports paired agreement, denominators, descriptive
intervals and disagreements. A human FAIL paired with judge PASS blocks the
critical gate. It never grants general quality qualification from these counts.

```powershell
& .venv/Scripts/python.exe -m workagent_rsi.human_calibration compare --labels <intake/human-labels.jsonl> --receipt <intake/submission-receipt.json> --decisions <frozen-judge-decisions.jsonl> --review-manifest <blind-review-pack/review-manifest.json> --output <new-agreement-report.json>
```

The later blind cohort needs at least20 natural finished artifacts from families
outside the development calibration families. Intake requires original source
references, domain, task instruction, input files and output hash. Real Office
libraries reopen supplied files. Controlled defect fixtures are refused as a
substitute for natural output. On 2026-10-25 the user authorized benchmark intake.
Twenty jobs were frozen (Excel10/Word7/PPT3). The user then approved twenty
generation requests. They initially produced17 real outputs (Excel9/Word6/PPT2),
with three runtime failures and no automatic retries. The user later approved
three model repairs and a separate deterministic PowerPoint assertion correction.
There are now20 natural outputs (Excel10/Word7/PPT3). All nine connected source
groups leave the adaptive/OOD splits before calibration. A complete review pack
contains the12 standards and20 natural outputs, with187 actual pages from30
complete renders. Two original workbooks exceed the forty-page render limit;
their original files remain available. There are still no submitted human
labels. See `benchmark_intake.md` and
`project_artifacts/formal_study/hardening_t26_t28_benchmark_intake.json`.
No reference workbook, fake file or agent-generated label fills that count.

Use `project_artifacts/results/hardening-v2/T28-benchmarks/20261025/complete-human-pack-v1/blind-review-pack/index.html`
for the complete32-case review. The earlier12-case and17-case packs remain
unchanged historical deliveries. No earlier review has been submitted.

Real model judging also needs a newly approved bounded policy. The previous27
request allowance, the20-request generation allowance and the separately
approved3-request repair allowance are exhausted. The extra PowerPoint correction
and rendering were separately approved and completed without a model request.
The server renders without a model. Existing
CLI protocol qualification does not imply this cohort has been judged or agrees
with humans. Missing labels, independent files or live authorization remain
explicit blockers rather than numeric accuracy.
