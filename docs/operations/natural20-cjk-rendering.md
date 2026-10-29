# Task-local Chinese font qualification

Natural artifact review exposed a rendering-environment defect: the frozen
Office image contained DejaVu and LibreOffice fonts but no CJK font. Actual
rendered Chinese prose appeared as missing-glyph boxes. Such rendering results
cannot establish that the Office artifact itself is defective.

The controller stopped its own judge process tree after detecting this defect.
Twelve cumulative model attempts and 545 charged/reserved seconds were retained,
including the interrupted request. Its token and tool telemetry is unavailable;
zero recorded tool calls is not proof of observed zero usage for that request.
Original decisions, ledgers and rendered pages remain historical evidence.

## Font delivery without changing the server image

The fix stages `NotoSansCJKsc-Regular.otf` as a read-only task input. Fontconfig
loads it through a task-local configuration and writes its cache under task
scratch space. No system font installation or full runtime copy is needed.
The original runtime fingerprint is unchanged. The font is about 16.4 MB;
the existing input, output, memory, network and cleanup boundaries remain active.

The font comes from the official `notofonts/noto-cjk` repository at revision
`f8d157532fbfaeda587e826d4cd5b21a49186f7c`. Its SHA-256 is
`2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b`.
The upstream SIL Open Font License 1.1 accompanies the font inside each task.
See the [font repository](https://github.com/notofonts/noto-cjk) and
[pinned license](https://github.com/notofonts/noto-cjk/blob/f8d157532fbfaeda587e826d4cd5b21a49186f7c/Sans/LICENSE).
The binary and generated pages stay in the local ignored result directory.

## Qualification and model boundary

Four original artifacts were rendered again, producing 22 pages. Fontconfig
selected the task-local font. The exported PDFs contain Chinese text and embed
Noto font subsets; an actual before/after page inspection confirmed readable
Chinese. Source artifact hashes, exported image hashes, resource limits and
cleanup were checked. This establishes CJK rendering for these four artifacts,
not general Microsoft Office layout parity.

Request preparation now rejects an output with CJK text unless its pages carry
the qualified font hash and font-selection evidence. Twenty-four focused checks
passed. The font qualification receipt is
`project_artifacts/formal_study/hardening_natural20_cjk_20261028.json`.

The user approved a new 92-request cohort bound to the corrected pages, with
104 cumulative attempts and 5400 cumulative seconds including prior failures.
The previous 545 seconds were not reset. Earlier opinions are not reused in the
new cohort. Manual follow-up remains waived and no human-ground-truth accuracy
claim is permitted.
