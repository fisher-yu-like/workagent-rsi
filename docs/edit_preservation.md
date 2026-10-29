# Authorized edit preservation

> Historical protocol snapshot. On 2026-10-29 the user replaced coded task acceptance with [task-level LLM review](operations/llm-task-review.md). Rule coverage, rule-authoring commands and per-criterion scoring below are historical records, not current run instructions. Native reading, rendering, transport and experiment controls remain where applicable.

`PreservationSpec` freezes the source SHA-256, explicit allowed operations,
preserved structural scopes and the versioned `office-structure-v1` policy.
Permissions are `replace`, `add` or `remove` on explicit path prefixes; wildcard
and traversal scopes are rejected. Protected scopes override edit permissions.

Excel paths include `excel/sheets`, `excel/sheet/<URL-escaped-name>/cell/A1`,
sheet state, merges and row/column dimensions. Cell values, formula text, number
formats and direct styles are compared. New-sheet permissions authorize content
within that new sheet, without authorizing changes to existing sheets.

Word paths include `word/paragraphs`, `word/tables`, `word/body_order`, sections,
headers and footers. Paragraphs retain text, style IDs, heading levels and direct
run formatting. Sequence alignment allows authorized insertions without treating
every following paragraph as replaced. A specific paragraph path uses its
one-based source sequence position. Table text and paragraph structure are kept.

PowerPoint paths include `powerpoint/slides`, `powerpoint/slide/<slide-id>/object/<shape-id>`,
object order and nested groups. Text, direct run formatting, geometry, table
text, image bytes and basic solid-fill facts are compared. Adding a slide can
authorize its new objects; existing slides remain protected by default.

Core timestamps, ZIP ordering and relationship serialization IDs do not form
business-content identity. Both source/output files are rehashed after inspection
and are never saved. The shared `preservation` check requires its source path/hash
in frozen `input_hashes` and emits source/output differences with authorization.

This is structural preservation, not complete visual equivalence. Complex Excel
charts/images/pivots/conditional formats/names/links, Word embedded objects/fields/
tracked changes/nested tables and PowerPoint charts or unknown objects create
explicit NEEDS_REVIEW records. A gap prevents an unconditional preservation pass.
Themes, inherited layout and rendered appearance require separate visual checks.
Bounds are 100 MiB per input, 50,000 structural facts/cells and 5,000 sequence
items. Comparison assumes trusted frozen policy and authorized input sources.
