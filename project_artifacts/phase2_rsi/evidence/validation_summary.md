# Phase 2 Validation Evidence

## Claim boundary

- Validation date: 2026-09-23, Asia/Shanghai.
- Branch: `codex/phase2-rsi`.
- Base commit: `e4dc4243546489d2843ec599daa1a777222aafc3`.
- Phase 2 contains architecture and experiment planning only. No dataset run, training run, benchmark score or promotion result is claimed.

## Environment

| Component | Version or path |
|---|---|
| Python | 3.12.10 via `py -3.12` |
| Bundled Node.js | 24.19.0 |
| Git | 2.52.0.windows.1 |
| Artifact runtime | Codex primary runtime bundle `26.905.11957` |
| DOCX renderer | Microsoft Word COM export to PDF |
| PDF rasterizer | Poppler `pdftoppm` from TeX Live 2026 |

## Final artifacts

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `reports/RSI整体框架与训练计划.docx` | 39,571 | `4A211AA696BDA5411F5AF3475BDA888C54835E1D183DF9F7DDC3D7C859654AC0` |
| `reports/RSI整体框架与训练计划.pptx` | 33,804 | `767E8D53C307A8B327055F2EE112CC3A544B84794F1DCD46D587F15D2F69BE4F` |
| `training_plan/experiment_matrix.xlsx` | 7,939 | `8546BB61696DE4E38932D988A85C2987DB0B42EAC932E7FE8D5E82A8F09D84AD` |
| `training_plan/resource_budget.xlsx` | 4,900 | `B3987263CD83EFA5383329D8DDEF9C82BD5BCD1CC8EE30548C9E3358B08ABE2E` |

## Office validation

- `python-docx` reopened the DOCX with 25 paragraphs and 2 tables.
- Microsoft Word exported the DOCX to a two-page PDF. Both pages were rasterized and inspected. A stranded section heading found in the first render was corrected with `keep_with_next`; the final two pages contain no clipping, overlap or orphaned heading.
- `python-pptx` reopened the PPTX with 9 slides. The finalizer receipt records package integrity, layout, approved font and first-party Artifact Tool import checks as passed. All 9 rendered slides were inspected.
- `openpyxl` reopened the experiment workbook with `Summary` and `Experiments` sheets and the resource workbook with one `Resource Budget` sheet.
- The experiment CSV and workbook agree on 12 planned experiments: 7 P0, 4 P1 and 1 P2. All experiment statuses remain `planned`.
- Both workbook formula scans matched zero error cells. The experiment workbook's 2 previews and resource workbook's 1 preview were inspected.
- Render evidence is preserved under `evidence/renders/`; machine-readable receipts are stored beside this file.

## Reproducibility checks

The final PPTX/XLSX build ran from `C:\Users\sy\Desktop`, outside the repository root, without a temporary `node_modules` junction or manually supplied runtime variables:

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" `
  "C:\Users\sy\Desktop\workagent-rsi\project_artifacts\phase2_rsi\training_plan\build_phase2_artifacts.mjs"
```

The builder derives the repository root from `import.meta.url`, discovers the installed presentations skill, locates the bundled Artifact Tool under the current user's Codex runtime, and supports environment-variable overrides.

Final project checks:

```powershell
py -3.12 -m pytest -q --basetemp="$env:TEMP\\workagent-rsi-pytest-final"
py -3.12 -m compileall -q src tests project_artifacts\phase1_harness\scripts project_artifacts\phase2_rsi
git diff --check
```

The recorded pre-commit result is 14 tests passed, zero compile errors and zero whitespace errors.

## Failed attempts retained for audit

1. A direct ESM build using only `NODE_PATH` exited with `ERR_MODULE_NOT_FOUND` for `@oai/artifact-tool`; Node ESM did not honor that lookup path.
2. A temporary junction allowed authoring but the presentation finalizer exited because `RUNTIME_NODE_MODULES` was not propagated to its import subprocess.
3. Supplying that variable produced valid artifacts, after which the builder was changed to discover and propagate the bundled runtime itself. The final clean-state command above exited successfully.

The failed attempts produced no promoted artifact and no training evidence.
