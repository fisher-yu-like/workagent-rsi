# Component Specifications

## Task validator

Input: JSON/YAML task document and input file manifest. Output: normalized `TaskSpec` or a list of validation violations. Checks required fields, file existence, risk level, hidden-test flag and evaluator configuration.

## Orchestrator

Input: `TaskSpec`, skill version, run configuration. Output: `RunResult` with state, trace id, artifact ids, evaluator report and failure reason. It owns transitions and invokes adapters but never rewrites evaluator rules.

## WorkAgent adapter

Input: normalized task and skill manifest. Output: ordered `AgentEvent` stream and final artifact references. A `MockWorkAgentAdapter` is required for deterministic contract tests; a real adapter is optional until provider access is available.

## Tool gateway and sandbox

Input: typed `ToolCall`. Output: typed `ToolResult`. Reject unknown tools, malformed arguments, disallowed paths, command injection patterns and budget exhaustion. Each invocation records start/end timestamps, exit status and output hashes.

## Artifact store

Input: byte stream or file path inside the run sandbox. Output: immutable `ArtifactRef` containing SHA-256, media type, size, run id and relative path. Artifact writes are atomic.

## Trace memory

Input: append-only `TraceEvent`. Output: queryable run timeline and failure summary. SQLite is the initial backend; JSONL export is mandatory for inspection.

## Evaluator

Input: task, artifacts, trace and pinned evaluator config. Output: `EvaluationReport` with critical gate, dimensions, score, violations and evidence pointers. It must be executable independently of the agent adapter.

