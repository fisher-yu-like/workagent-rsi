# Natural20 automatic review

Current update:font qualification exposed and fixed missing Chinese glyphs. See `natural20-cjk-rendering.md`. The user approved a fresh92-request cohort,manifest af7f6da0...a6121c0,with104cumulativeattempts/5400seconds including12historicalattempts/545seconds. Earlier plans below are historical.

The user requested completion of evidence preparation and automatic judging.
The additional manual follow-up remains waived. Historical human labels stay
provisional and are not supplied to the model.

## Evidence preparation

Both workbook render gaps were recovered from the original hash-verified
workbooks in the existing Apptainer Office worker. They produced 48 and 96
actual pages. The new PNG exports total about 7.4 MB. Both worker traces confirm
resource limits and cleanup. No server installation was performed; the default
renderer still has its original forty-page cap. The separately bounded recovery
jobs used a hundred-page cap and 180-second timeout, with the existing 32 MiB
export limit and 2 GiB memory limit.

All twenty natural cases now have 311 actual output pages. Some pages have
identical image hashes; they are still retained at their actual page locations.
Four input parsing warnings were audited by preserving the original chart,
drawing and validation XML. This does not establish recalculated formula values
or embedded-image appearance. These limitations remain explicit.

Source cell observations are compacted without selecting only favorable cells.
For Excel outputs, an explicit delta reconstructs every extracted output cell
from the original input baseline plus additions, changes and deletions. The
reconstruction is checked before request preparation. Other content retains its
original extraction order. No workbook is rewritten.

## Request protocol

The plan has twenty semantic checks, fifty-two overlapping visual batches and
twenty cross-channel consistency checks. Adjacent visual batches share a page.
The consistency reports are not independent factual sources. A later report
cannot override a mandatory earlier FAIL or PARTIAL. Missing or uncertain
evidence retains INCOMPLETE. A declared-scope PASS does not grant reviewed
whole-task acceptance or human-calibrated accuracy qualification.

No human labels or reference answers are included. Every input, page, request
template and execution-code hash is frozen. Tools and automatic retries are
disabled. Continuation requires the exact attempted prefix and shared budget;
successful requests cannot be replayed as new independent results. A missing
parent causes its dependent consistency request to remain unavailable without
spending a model call.

## First attempt and correction

The first authorized request used 59 charged seconds and returned a structured
decision, but strict source-quote validation rejected it. Formula quotes were
JSON-escaped in the supplied source text; two of six returned source citations
did not match those escaped strings. The raw opinion is preserved as an invalid
attempt and has not been admitted or reused.

The revised plan exposes formulas and prose verbatim. Native XML is supplied as
distinct exact-citable sources. The same six source citations match the revised
literal sources in an offline format diagnostic; this check does not convert
the old model opinion into a valid result. Twenty-three focused tests passed,
including historical-budget carryover and strict citation-format controls.

The revised manifest is under
`project_artifacts/results/hardening-v2/T28-natural-judge/20261028/prepared-literal-v2/`.
It still contains 92 requests. Running it requires the separately requested
approval to replace the prior unused allowance and raise cumulative attempts
from 92 to 93, including the preserved failed attempt. Cumulative model time
remains 5400 seconds, including the 59 seconds already charged. Each request has
a 120-second limit. The 4096 output-token instruction is not a CLI server cap.

Current evidence and approval status are recorded in
`project_artifacts/formal_study/hardening_natural20_steps12_20261028.json`.
