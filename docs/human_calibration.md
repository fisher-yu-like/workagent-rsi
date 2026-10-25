# Development calibration and human review

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
generation requests. They produced17 real outputs (Excel9/Word6/PPT2), with
three runtime failures and no retries. There are still no submitted human
labels. All nine connected source groups leave the adaptive/OOD splits before
calibration. A natural-only review pack contains the17 outputs and126 actual
pages from15 complete renders; two workbooks exceed the forty-page render
limit. It retains the20-file shortage blocker. See `benchmark_intake.md` and
`project_artifacts/formal_study/hardening_t26_t28_benchmark_intake.json`.
No reference workbook, fake file or agent-generated label fills that count.

Real model judging also needs a newly approved bounded policy. The previous27
request allowance and the new20-request generation allowance are exhausted.
Three repair requests are proposed separately and remain unapproved. The
server renders without a model. Existing
CLI protocol qualification does not imply this cohort has been judged or agrees
with humans. Missing labels, independent files or live authorization remain
explicit blockers rather than numeric accuracy.
