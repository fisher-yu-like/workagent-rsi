# Implementation Backlog

1. Create `pyproject.toml`, package metadata and a single `tests/` root.
2. Implement Pydantic contracts for tasks, manifests, traces, artifacts and reports.
3. Implement SQLite state/trace store and content-addressed artifact store.
4. Implement tool gateway with allowlist, timeouts and path checks.
5. Implement deterministic mock WorkAgent adapter.
6. Implement orchestrator state machine, retry and resume behavior.
7. Implement critical evaluator gates and Markdown/JSON/CSV report generation.
8. Add smoke, complete and controlled-failure fixtures.
9. Add optional Excel/Word/PPT adapters with explicit dependency detection.
10. Run static checks, unit/integration tests, smoke test and real adapter checks where available.
11. Generate Office reports only from actual run evidence.

