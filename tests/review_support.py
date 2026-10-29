"""Independent review fixtures and observations; no scoring oracle is inferred."""

import json
from pathlib import Path

from workagent_rsi.assessment_contracts import AcceptanceSpec, Location, Requirement


def requirement(check, expected, *, description="Frozen review requirement", **location):
    return Requirement(
        requirement_id="required", description=description, check=check,
        expected=expected, location=Location(artifact="output", **location),
        critical=True, dimension="correctness", evidence_source="independent review task",
    )


def specification(domain, *requirements, task_id="review", **kwargs):
    return AcceptanceSpec(
        task_id=task_id, version="review-1", artifacts={"output": domain},
        requirements=list(requirements), dimension_weights={"correctness": 1}, **kwargs,
    )


def observe(root, case_id, **values):
    """Write before asserting, so a failed regression retains its actual evidence."""
    payload = {
        "case_id": case_id,
        **{key: value.model_dump(mode="json") if hasattr(value, "model_dump") else value
           for key, value in values.items()},
    }
    Path(root, "observation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
