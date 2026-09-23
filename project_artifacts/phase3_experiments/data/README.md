# Phase 3 Data Layer

Run from the repository root with Python 3.12:

```powershell
py -3.12 project_artifacts/phase3_experiments/data/generate_dataset.py
py -3.12 project_artifacts/phase3_experiments/data/quality_check.py
```

The generator writes raw, processed, split and protected JSONL layers plus `provenance.json`. The quality checker writes `quality_report.json` and exits non-zero on schema, count, duplicate or leakage-boundary failures.
