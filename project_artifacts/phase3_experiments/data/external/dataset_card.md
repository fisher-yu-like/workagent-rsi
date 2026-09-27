# External Dataset Card (Gate Version)

## Status

No external task files have been admitted to the formal study as of the current
gate. The repository contains only the candidate metadata in `source_manifest.json`.
The existing 30-task fixture remains `project-generated` and is not relabelled.

## Intended use

The first formal candidate is SpreadsheetBench for an Excel-only protocol because
it has a published data statement and an explicit CC BY-SA 4.0 statement. OfficeBench
is reserved for a later three-application transfer study after its data terms are
confirmed. OSWorld and Windows Agent Arena are environment-transfer candidates, not
drop-in file datasets.

## Required processing once licensed

1. Keep an immutable `raw` archive with URL, retrieval time, checksum and license text.
2. Normalize tasks into the project contract without copying hidden answers into the
   candidate workspace.
3. Group near-duplicates and source families before evolve/develop/regression/hidden/OOD
   splitting.
4. Run schema, Office-package, duplicate, leakage, sensitive-content and license checks.
5. Publish only an allowed public subset; keep hidden inputs and expected outputs out of
   provider-facing workspaces.

## Known limitations

Repository-level SPDX metadata does not settle the rights to every spreadsheet,
screenshot, VM image or answer file. Formal claims must name the exact release and
file-level provenance, not only the GitHub repository.
