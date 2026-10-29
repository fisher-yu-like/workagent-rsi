# Evidence scope and independent reviews (T16)

> Historical protocol snapshot. On 2026-10-29 the user replaced coded task acceptance with [task-level LLM review](operations/llm-task-review.md). Rule coverage, rule-authoring commands and per-criterion scoring below are historical records, not current run instructions. Native reading, rendering, transport and experiment controls remain where applicable.

Semantic review partitions supported extracted evidence within the fixed
character, item and partition limits. Each partition preserves evidence IDs and
locations. Evidence outside the requested location is listed as excluded; an
oversized required item is listed as uncovered. No partial extraction can
establish a pass. Extraction has a separate hard limit of 2,000,000 characters
and 20,000 items to bound memory before partitioning. A requirement that exceeds
those limits remains unavailable.

Every selected item needs a valid exact citation. The channel records required
and checked evidence separately from the quality decision. Partition summaries
are checked in a bounded reduction tree for consistency against the same
requirement. Summaries describe earlier reviews; they do not create independent
facts. If the budget cannot combine summaries, local coverage can be complete
while cross-partition consistency remains unknown and the result needs review.

Sources are supplied by the trusted caller as `AuthorizedSource` values with
an ID, inline text, its UTF-8 SHA-256 and a reference. They are not loaded from
artifact instructions or arbitrary paths. `options.verify_sources=true`
requires these sources and exact source citations in every observation.
An output quote alone cannot establish source accuracy. Source hashes affect
the assessment identity and decision cache. A source text budget is checked
separately against `max_chars`; it is not silently truncated. Sources and
rubrics still need independent human ownership. A matching quote does not
prove that the judge reasoned correctly.

`options.required_content_channels` explicitly declares extraction scope.
Supported channels are `body_text` for Word, `worksheet_cells` for Excel and
`slide_content` for PowerPoint. Required headers, footers, notes or image text
return review gaps. Missing extracted content does not prove its absence in
the original. Formula strings remain distinct from recalculated values.

Visual checks retain T15's complete page batches. They assess per-page evidence
by default. Requirements about cross-page consistency can set
`cross_partition_consistency=true` and explicit `consistency_groups` of page
IDs. Each group receives the actual images together within the image budget;
the groups must cover and connect all required pages. Disconnected or oversized
groups remain review gaps. These checks establish only the declared joint-image
comparisons, not the accuracy of an uncalibrated visual model.

Both channels accept `independent_review=True` to bypass the decision cache.
`ModelReviewConfig.independent_review=true` disables both decision caches in
the configured factory. Rendering/extraction reuse does not count as a model
review. Cache hits contribute zero current calls and zero independent reviews;
historical `JudgeResult` values are retained as `reused_judge_result`.

The model provider saves every raw and validated repeat decision, identity,
citations, attempt and disagreement. `JudgeResult` exposes all successful
reviews, actual invocation attempts and the combined decision. Self-reported
confidence is labelled `uncalibrated_self_report`; it is not a measured
probability. Retried attempts and accepted independent reviews have separate
counts. Evidence content is inline untrusted data and cannot replace the fixed
rubric. Offline injection tests verify request boundaries and failure handling.
Real model resistance to injection still requires empirical qualification.

## Remaining qualification

T16 local protocol tests use authored Office files and injected CLI/API/image
providers. No remote API, model, Office worker or SSH call is made by this phase.
`capability_report()` returns `not_probed` for configured live capabilities.
Configuration and a passing unit transport do not qualify Responses, structured
output or image judgement. T16's initial local delivery remained partial until
the separately performed real probes below. Real decision accuracy and human-label
calibration remain T28 work.

The 2026-10-24 real CLI gpt-6.1-sol controls passed authorized-source agreement,
source contradiction, artifact instruction injection, missing-source rejection,
cache reuse with zero current calls/independent reviews, a fresh independent
review, evidence partitions and summary consistency. Actual joint-image local
and consistency reviews also passed. Raw requests, decisions, identities and
usage are retained; direct API /responses and other providers stay not_probed.
The CLI used an invocation-local OpenAI-auth provider alias with zero automatic
request/stream retries and the approved shared call/time budget.

The real long-deck check exposed an unscoped visual batch requirement. Its
repair passed84 related tests; a separately approved three-request real recheck
passed with two readable batches accepted and page17 rejected. T15/T16 are
qualified for the recorded frozen worker and CLI configuration.
These authored protocol controls do not establish calibrated accuracy.
