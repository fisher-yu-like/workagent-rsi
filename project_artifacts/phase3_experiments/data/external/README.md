# External Data Gate

This directory is the controlled entry point for externally sourced Office-agent data.
At the current gate, it contains metadata only. No benchmark task file, spreadsheet,
document, screenshot, VM image, or cached answer is copied here until the manifest
records a source-specific license decision.

The gate distinguishes the license of a code repository from the license of the
benchmark data. A permissive code license is not evidence that the task files or
third-party Office content can be redistributed. `source_manifest.json` is the
authoritative record used by `quality_check_external.py`.

## Candidate order

1. SpreadsheetBench: strongest initial candidate for an Excel-only study. The official
   README states CC BY-SA 4.0 and publishes a 912-instruction benchmark, but each
   forum-derived workbook still needs provenance and redistribution review.
2. OfficeBench: best coverage for a three-application workflow. The official code
   repository is Apache-2.0, while the task/data license is not separately stated;
   it remains metadata-only pending author/data confirmation.
3. OSWorld: useful for desktop execution transfer. The code is Apache-2.0, but the
   VM, downloaded files and application licenses are separate obligations.
4. Windows Agent Arena: useful for Windows/Office execution, but Windows evaluation
   images and Office assets require Microsoft terms review; it is not a drop-in data
   source for the formal study.
5. SpreadsheetBench-2: metadata only because the official repository does not expose
   a license in its GitHub metadata.

## Entry requirements

Before a candidate can enter `raw/` or a formal result:

- official URL, paper/version and retrieval timestamp are recorded;
- data-specific license text or written permission is captured;
- checksum and file inventory are recorded;
- third-party and personal-data restrictions are reviewed;
- task schema, duplicate groups and split families pass the quality checker;
- hidden/OOD exports are separated from candidate-facing workspaces.

The current verification snapshot is in `source_verification.json`. It confirms
repository-level metadata and one README-level data statement, but does not yet
confirm workbook-level provenance. Until all requirements are true, the quality
gate must fail closed and the fetch script may create only a metadata report.
