# Public Office score semantics (T17)

> Historical protocol snapshot. On 2026-10-29 the user replaced coded task acceptance with [task-level LLM review](operations/llm-task-review.md). Rule coverage, rule-authoring commands and per-criterion scoring below are historical records, not current run instructions. Native reading, rendering, transport and experiment controls remain where applicable.

T20 adds separate execution/task success denominators while preserving null
unobserved artifact quality. See [execution failure feedback](execution_failure_feedback.md).

Normal Office evaluation through Check, Harness, OfficeArtifactEvaluator and the
artifact RSI evaluators uses the shared evidence snapshot and versioned task
admission. `spec_from_task` now defaults unprofiled task constraints to
`task_acceptance`. A readable file or a set of passing declared checks does not
establish reviewed task completeness. Without a task-bound reviewed inventory,
the task remains incomplete and its quality remains null.

The public `AssessmentOutcome` exposes separate fields:

| Field | Meaning |
|---|---|
| task_acceptance | PASS, FAIL, INCOMPLETE or NOT_ASSESSED for the whole task |
| quality_score | Observed task quality on a 0 to 1 scale, otherwise null |
| spec_admission | Task/spec review and admission, including missing obligations |
| task_requirement_coverage | Reviewed mandatory obligations covered by checks |
| check_completion | Declared checks actually completed, including known failures |

`EvaluationReport` exposes the outcome plus task_acceptance and quality_score.
For `score_semantics=task-v2`, its compatibility `passed` and `score` fields must
match that outcome. The library rejects inconsistent success fields. ScoreReport
uses a 0 to 100 scale and marks `score_semantics=task-assessment-v2` for new
profiles. Its `task_score` and `quality_score` share task-quality semantics.

A known critical failure blocks acceptance even when its weight is zero and
the raw weighted quality is 100. A missing channel leaves total quality null,
while known dimensions and confirmed failures remain visible. Structural-only
profiles report NOT_ASSESSED for task acceptance. Unknown channels never disappear
from the denominator or cause remaining weights to be silently renormalized.

Check, Harness and RSI use the same source-bound assessment identity and spec
construction. Check accepts a report_root and creates a fresh report directory
for each call. Harness verifies stored artifact hashes, uses read-only assessment
copies and writes score, evidence and issue reports from a single snapshot.
RSI rows retain task acceptance, admission and both coverage measures. Missing
or inconsistent reports cannot authorize a complete task result.

## Explicit compatibility

Historical Office evaluation can be requested with
`assessment_profile="legacy"` on Check.evaluate, OfficeArtifactEvaluator,
Harness or a frozen evaluator. The CLI provides `--assessment-profile legacy`.
Legacy contract mode in FrozenEvaluator explicitly selects the historical
evaluator. Compatibility results are labelled legacy, and their task acceptance
remains NOT_ASSESSED. They do not qualify whole-task success or research claims.

The low-level `assess(AcceptanceSpec(...), ...)` contract still accepts a v1 spec
whose evaluation_profile is explicitly absent/null. Its old total_score and
acceptance_status fields describe declared checks and are labelled
declared-check-v1. Its new task_acceptance remains NOT_ASSESSED and task quality
remains null. Callers needing task acceptance must supply a reviewed task profile.
This compatibility contract does not override the strict defaults at task entry
points. Non-Office smoke tests remain a separate mechanism qualification path.

Old JSON files are never rewritten. The legacy outcome adapter preserves its
historical interpretation when no versioned outcome exists; when a new outcome
is present it validates and returns that explicit record. Tests of historical
pilot mechanics now opt into legacy semantics rather than receiving an implicit
task-success claim from the normal entry point.

## Evidence boundary

The parity tests use independently authored XLSX values and review receipts,
real OOXML files and an injected execution adapter. They compare Check, Harness
and WorkAgent RSI identity, score and acceptance on the same bytes. Other cases
cover missing review, structural-only checks, critical zero-weight failures,
missing visual capability, reference hash changes and malformed success fields.
No Office process, remote execution or model call is used. T08/T13/T15/T16 real
qualification remains deferred; unavailable capabilities remain explicit gaps.
