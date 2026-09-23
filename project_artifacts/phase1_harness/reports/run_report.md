# Phase 1B Mock Pipeline Run Report

- Git commit: `8e8377cce2f87ac76c6fa1a96e8a3dab261e29ca`
- Python: `3.12.10`
- Platform: `Windows-11-10.0.26200-SP0`
- Working directory: `C:\Users\sy\Desktop\workagent-rsi`
- Adapter: `MockWorkAgentAdapter` (real external WorkAgent provider is not configured)

## Results

| Case | State | Run ID | Duration (s) | Evidence |
|---|---|---|---:|---|
| minimal_success | SUCCEEDED | `run-800e181b7ffc` | 0.057019 | `results/minimal_success/result.json` |
| complete_success | SUCCEEDED | `run-b765a2399b4b` | 0.058696 | `results/complete_success/result.json` |
| controlled_failure | FAILED | `run-260ed93c619b` | 0.047073 | `results/controlled_failure/result.json` |

## Limitations

This report proves the local Harness contracts, trace persistence, artifact storage, evaluation and failure path using a deterministic mock adapter. It is not evidence that an external WorkAgent provider or real Office application executed successfully.
