# Interfaces

The signatures below are the Phase 1A contract. Concrete implementations belong to Phase 1B.

```python
from dataclasses import dataclass
from typing import Iterable, Mapping, Protocol, Sequence

@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    domain: str
    instruction: str
    input_files: tuple[str, ...]
    expected_constraints: Mapping[str, object]
    risk_level: str
    hidden_test: bool

@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    path: str
    sha256: str
    media_type: str
    size_bytes: int

@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: Mapping[str, object]

@dataclass(frozen=True)
class ToolResult:
    ok: bool
    output: Mapping[str, object]
    error: str | None = None

class WorkAgentAdapter(Protocol):
    def execute(self, task: TaskSpec, skill_id: str) -> Iterable[Mapping[str, object]]: ...

class ToolGateway(Protocol):
    def invoke(self, call: ToolCall) -> ToolResult: ...

class Evaluator(Protocol):
    def evaluate(self, task: TaskSpec, artifacts: Sequence[ArtifactRef], trace_id: str) -> Mapping[str, object]: ...

class Orchestrator(Protocol):
    def run(self, task: TaskSpec, skill_id: str) -> Mapping[str, object]: ...
    def resume(self, run_id: str) -> Mapping[str, object]: ...
```

## Skill manifest minimum

The Phase 1B manifest schema must contain `id`, `version`, `domain`, `description`, `triggers`, `inputs`, `outputs`, `tools`, `preconditions`, `postconditions`, `risk_level`, `dependencies`, `tests`, `evaluator_config` and `rollback_policy`.

