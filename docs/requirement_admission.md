# Task requirement admission (T10)

Check completion and task requirement coverage are separate facts. A readable
Office file, or a perfect score on the supplied checks, does not establish that
all user obligations were tested. No artifact is read to construct the inventory.

New specifications select one of three evaluation profiles:

- `structural_only`: keep declared-check observations and `check_score`;
  `task_score` and `total_score` are null, `task_acceptance=NOT_ASSESSED`.
- `task_acceptance`: a reviewed task-bound inventory must cover all mandatory
  obligations with applicable check IDs before a task score is admitted.
- `research`: the same coverage boundary and independent review provenance;
  model self-review cannot admit a research claim. Separate dataset, runtime,
  evaluator calibration and cohort gates still apply.

Each `TaskRequirement` records requirement_id, verbatim source_quote, source_ref,
obligation, mandatory, validation_method and check_ids. Supported source refs
are `task.instruction` and `input:<zero-based-index>` for an authorized UTF-8
task input frozen in `spec.input_hashes`. Input quote reads are bounded to 1 MiB;
other sources/formats require an explicit future adapter, not invented quotes.

`RequirementInventory` records task_id, requirements, reviewed and provenance.
The trusted review receipt contains kind (`human_review` or `reviewed_benchmark`),
reviewer, review_ref, task_hash and spec_hash. `task_fingerprint(task)` binds the
actual instruction/domain/task ID and current authorized input hashes.
`spec_coverage_fingerprint(spec)` binds the frozen checks, expectations,
locations, weights and input hashes, excluding the receipt/profile/context to
avoid a circular digest. Freeze these before assessing candidate artifacts.
Changing inputs, task text or check semantics invalidates the review binding.

`validate_spec_coverage(task, inventory, spec, evaluation_profile=...)` returns a
`SpecAdmissionReport` with reasons, mappings, uncovered IDs and mandatory/covered
counts. Missing review, unknown check IDs, inapplicable mapped checks, mismatched
validation methods, invalid quotes or missing mandatory coverage yield
`SPEC_INCOMPLETE`. `Assessment` and `ScoreReport` retain this report; requirement
coverage never borrows the check-completion denominator. Missing admission keeps
task score null and task acceptance incomplete. Declared-check observations
remain available for diagnosis.

Review authenticity and semantic completeness belong to the trusted review
process. Hash validation proves consistency with that receipt; it cannot prove
that a supplied reviewer identity is authentic or that a human found every
obligation. The program does not manufacture review from a model's assertion.

## Compatibility and entry points

An explicit old v1 spec without a profile is marked `LEGACY_UNREVIEWED`.
Its existing `total_score` / `acceptance_status` remain declared-check fields
for compatibility, with an explicit scope note. Its new `task_score` is null
and `task_acceptance=NOT_ASSESSED`; it has no task-coverage admission. Migration
of all legacy downstream score consumers is owned by T17, not implied by T10.

`spec_from_task` with no constraints defaults to `task_acceptance`, so an
unconstrained analysis task cannot obtain full acceptance from readability.
Legacy constraint adapters remain visibly unreviewed. Supplying a profile and
inventory opts them into admission. Nested acceptance specs cannot replace the
actual caller task context. Existing project-generated sales checks remain
declared-check qualification evidence unless separately reviewed.

Reports show task acceptance/quality, declared-check quality, check completion
and requirement admission separately. Test fixtures and receipts used in T10
are authored local engineering cases, not real external benchmark admission.
