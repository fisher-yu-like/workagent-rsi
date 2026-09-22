# Environment Inventory

| Item | Observed value | Impact |
|---|---|---|
| OS/shell | Windows / PowerShell | Scripts should work from PowerShell and record commands verbatim. |
| Preferred Python | `py -3.12` -> Python 3.12.10 | Use for package creation and tests. |
| Legacy default Python | `python` -> Anaconda Python 3.7 | Do not rely on unqualified `python`. |
| Git | `D:\Git\cmd\git.exe` | Initialize local repository and record commits. |
| LibreOffice | Not found on PATH | Add optional adapter and explicit blocked status until installed. |
| Browser/network | Network retrieval succeeded for arXiv HTML | Sources are preserved locally for provenance. |
| Existing dependencies | None declared | Phase 1B must add a minimal `pyproject.toml` and lock policy. |

## Required Phase 1B dependency policy

- Python >= 3.11.
- Pydantic for contract validation.
- Typer for CLI.
- pytest for unit/integration tests, all under one top-level `tests/` directory.
- SQLite from the standard library for initial trace/registry persistence.
- `openpyxl`, `python-docx`, and `python-pptx` only where their respective adapters need them.
- LibreOffice headless remains optional but is required for claims involving formula recalculation or rendered visual QA.

