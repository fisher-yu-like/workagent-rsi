# Slide visibility and page coverage (T15)

> Historical protocol snapshot. On 2026-10-29 the user replaced coded task acceptance with [task-level LLM review](operations/llm-task-review.md). Rule coverage, rule-authoring commands and per-criterion scoring below are historical records, not current run instructions. Native reading, rendering, transport and experiment controls remain where applicable.

`inspect_visibility(deck, slide_index)` reports object IDs, slide-space geometry,
certainty and the reason for review. Group offsets and scales are transformed
before bounds checks. A required text occurrence outside the canvas cannot
establish delivery. Rotation, explicit opacity/hidden attributes, white text
and possible foreground coverage produce `NEEDS_REVIEW` when they affect the
only matching occurrence. A clear duplicate can satisfy the text requirement.

`powerpoint.bounds` checks certain overflow; uncertain transforms require
review. `powerpoint.overlap` reports possible occlusion, including a later
filled object that fully contains the text. An empty background painted before
the content is legal. Images do not acquire a text-absence defect simply
because there is no extracted text. An explicit text requirement still needs
its declared evidence; this geometry channel does not perform OCR.

These are structural checks. Theme inheritance, masks, complex transforms,
decorative shapes, transparency and paint order can change the final appearance.
Risk findings request rendered review; their presence does not establish that
the final image is defective. A geometry pass does not establish visual quality.
`powerpoint.object_text` continues to check the declared object's text value;
tasks requiring visibility must declare the visibility/visual requirement.

`VisualCoverageLedger` separates required, rendered and checked pages. Page IDs
must be unique positive integers; a checked page must have a rendering.
Its `report()` includes completeness, missing render pages and unchecked pages.
Completeness records evidence coverage and does not imply quality acceptance.

`VisualAssessmentChannel` renders once and partitions every required page in
the declared order into batches bounded by `max_images_per_check`. The default
uses every rendered page; explicit `options.pages` defines a required subset.
A zero budget disables model calls. Every observation must reference a supplied
image ID and its exact artifact location. Missing citations prevent full
completion. A failing later batch retains the earlier page coverage and actual
call count. A fully cited `NEEDS_REVIEW` decision counts as checked evidence,
while its quality score remains null. Across complete batches the least
completion value is used; this all-pages rule is conservative and does not
establish cross-page semantic consistency (T16).

Cache keys bind the artifact, requirement, provider/renderer identities, image
hashes, page IDs and artifact locations. Identical-looking pages in different
batches cannot reuse one another's locations. Cached decisions are revalidated
and contribute zero independent model calls.

The v2 batch protocol sends a copy of the requirement scoped to the attached
pages only. It retains the original requirement hash and global required pages
in `batch_scope`; the enclosing evaluator owns global coverage. Local requests
omit consistency groups, while a consistency request contains only its attached
group. The original requirement is unchanged. The protocol identity changed so
old unscoped cached decisions cannot satisfy a corrected request.

The first actual 2026-10-24 probe rendered all 24 authored control/long-deck
pages on the frozen worker. CLI gpt-6.1-sol rejected off-canvas, white-on-white
and opaque-cover controls, and accepted readable rotation, transparent cover
and legal-background controls. It cited all 17 long-deck pages but returned
NEEDS_REVIEW because each batch still declared all 17 pages. This real finding
produced four failing offline regression cases. They now pass along with 80
existing related tests. The separately approved three-request real recheck then
passed: pages1-8 PASS, pages9-16 PASS, page17 FAIL. All17 pages were cited and
global coverage was complete. Existing pre-fix records remain preserved.

## Qualification scope

The local suite uses authored PPTX geometry and injected rendering/judgement
fixtures, including a 17-page coverage example. It makes no server, Office or
model call. R03/R04 now conservatively reject or request review; this is not a
measurement of calibrated visual judgement accuracy. The T15 manifest also
indexes actual frozen Office rendering, authored annotations, CLI controls and
the corrected real batch-scope recheck.

When the server is available, retain an immutable worker/image identity and:

1. Render authored off-canvas, white-on-white, later filled cover, rotated,
   transparent and legal-background decks through the isolated T05 worker.
2. Save source/output hashes, actual page images and rendering manifest; verify
   the source remains unchanged and owned worker processes are cleaned up.
3. Obtain independent page/region annotations and compare findings with those
   annotations. Do not use geometry results as the annotations.
4. Check every required page of a long document/deck, including a defect on the
   last page and a failed final batch. Record the complete coverage ledger.
5. Qualify the image judge separately under the live-call policy before any
   model request. Preserve raw decisions, locations and actual call counts.

T05's earlier rendering probe does not qualify this new T15 behaviour. T16/T28
own cross-partition reasoning and judge calibration; T17 owns the remaining
legacy consumer/score migration.
