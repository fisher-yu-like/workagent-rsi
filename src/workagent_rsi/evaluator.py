from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .contracts import ArtifactRef, EvaluationReport, TaskSpec


class BasicEvaluator:
    """Initial deterministic evaluator; Office-specific evaluators are Phase 1B follow-ups."""

    def evaluate(self, task: TaskSpec, artifacts: Sequence[ArtifactRef], trace_id: str) -> EvaluationReport:
        failures: list[str] = []
        evidence: list[str] = []
        if not artifacts:
            failures.append("no artifacts produced")
        content = b"".join(Path(ref.path).read_bytes() for ref in artifacts)
        required = task.expected_constraints.get("required_text")
        if required is not None and str(required).encode("utf-8") not in content:
            failures.append(f"required text missing: {required}")
        for ref in artifacts:
            evidence.append(f"artifact:{ref.artifact_id}")
        passed = not failures
        return EvaluationReport(
            passed=passed,
            score=1.0 if passed else 0.0,
            critical_failures=failures,
            dimensions={"structural_correctness": 1.0 if passed else 0.0},
            evidence=evidence + [f"trace:{trace_id}"],
        )

