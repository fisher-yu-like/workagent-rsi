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
substitute for natural output. No such independent files are currently available;
the user will provide them later. No fake files or labels fill that count.

Real model judging also needs a newly approved bounded policy; the previous27
request allowance is exhausted. The server renders without a model. Existing
CLI protocol qualification does not imply this cohort has been judged or agrees
with humans. Missing labels, independent files or live authorization remain
explicit blockers rather than numeric accuracy.
