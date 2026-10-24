# Actionable issue evidence (T18)

The verifier reads the existing Assessment snapshot. It does not reopen or edit
artifacts and does not call a model. Each new issue preserves the independently
declared expected value, actual observation, requested and observed locations,
artifact hashes and evidence references. Confirmed defects remain separate from
specification and assessment gaps.

New fields describe the next action without inventing a cause:

| Field | Meaning |
|---|---|
| failure_origin | artifact_defect, spec_gap or assessment_gap |
| affected_requirements | Requirements whose fulfillment or assessment is affected |
| repair_action | Target, grounded description, edit locations and evidence references |
| verification_steps | Repeat the frozen check, compare evidence, then recheck mandatory and preservation criteria |
| impact | Consequence for acceptance, assessment completeness or a declared quality dimension |

An artifact action names the affected logical locations. A capability or spec
action has no artifact edit locations. The contract checks that the action target
matches the failure origin and cites the issue's own evidence. Legacy location
and repair_hint remain available; new repair_hint mirrors the action wording.
Historical issues without these fields remain readable, with no invented action
or origin added by parsing.

For a wrong total, the issue retains both numbers and the worksheet/cell. Its
action requests recomputation from authorized records and its steps name the
frozen criterion. A visual channel gap requests rendering and qualified review;
it does not recommend deleting text or changing correct content. Unsupported
check configuration targets the specification owner. Missing reviewed task
admission produces a separate evaluation-only spec issue even if every declared
check passes. Its `spec-admission:<hash>` evidence reference resolves to the
Assessment.spec_admission record and binds its serialized content.

Issue IDs depend on task, requirement ID, check and requested location. Adding
an unrelated check or observing a different incorrect value does not change
that issue ID. Changes to the task cohort/spec still require the existing
comparison identity gates. Grouping uses requirement IDs and does not assert a
shared root cause. Per-requirement scoring is unchanged. The verifier leaves
cause_hypothesis null; T19 owns trace-supported diagnoses and their limits.

General feedback does not contain internal fixture answer knobs. New defect
actions use check-specific wording rather than replaying arbitrary hints. A
skill_improvement_hint is retained only when the frozen requirement explicitly
sets `options.qualification_only=true`; the issue carries the same flag.
Historical unmarked knob advice is filtered when projected into candidate
feedback. Expected/observed artifact data remains data and is not rewritten into
instructions. T16's instruction boundary continues to apply.

The feedback projection allowlists the new fields and nested action/location
fields, strips protected metadata, and excludes evaluation-only issues and gaps.
This prevents specification fixes or missing judge capabilities from becoming
artifact repair instructions. The offline ArtifactFeedbackProvider now uses its
own fixed requirement-class mapping and writes qualification.json. It is marked
qualification_only and is a test policy, not a real model improvement result.
Formal-run rejection of qualification-only providers remains T23 work.

Local tests use authored XLSX defects, missing-channel/spec controls and frozen
snapshots, including verification after the original file changes. They establish
report facts and feedback boundaries. They do not establish real agent repair
efficacy; the repair loop and empirical validation remain later tasks.
