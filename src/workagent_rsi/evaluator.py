from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import tempfile
from typing import Sequence

from .contracts import ArtifactRef, EvaluationReport, TaskSpec
from .office_checks import MEDIA_TYPES, inspect_office_file


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


class OfficeArtifactEvaluator:
    """Reopen genuine Office packages and run deterministic file-level checks."""

    VERSION = "office-evaluator-v2"
    MEDIA_TYPES = MEDIA_TYPES

    @classmethod
    def evaluator_hash(cls) -> str:
        """Hash the evaluator source files used for a report identity."""

        digest = hashlib.sha256()
        for name in ("evaluator.py", "office_checks.py", "render_checks.py"):
            source = Path(__file__).with_name(name)
            digest.update(name.encode("utf-8"))
            digest.update(source.read_bytes())
        return digest.hexdigest()

    def evaluate(self, task: TaskSpec, artifacts: Sequence[ArtifactRef], trace_id: str) -> EvaluationReport:
        failures: list[str] = []
        warnings: list[str] = []
        evidence: list[str] = []
        channel_status: dict[str, str] = {}
        dimension_values: dict[str, list[float]] = {}
        expected_media_type = self.MEDIA_TYPES.get(task.domain.lower())
        if not artifacts:
            failures.append("no artifacts produced")
        for ref in artifacts:
            path = Path(ref.path)
            evidence.append(f"artifact:{ref.artifact_id}")
            if expected_media_type is None or not ref.media_type.startswith(expected_media_type):
                failures.append(f"unexpected format for {task.domain}: {ref.media_type}")
                continue
            if not path.exists():
                failures.append(f"artifact path does not exist: {path}")
                continue
            # The store hash is retained as provenance.  Older callers may
            # construct test refs with a placeholder hash, so a mismatch is a
            # warning while the freshly computed file hash remains evidence.
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            evidence.append(f"artifact_sha256:{actual_hash}")
            if ref.sha256 and ref.sha256 != actual_hash:
                warnings.append(f"artifact hash differs from supplied reference: {ref.artifact_id}")
            suffix = {"excel": ".xlsx", "word": ".docx", "powerpoint": ".pptx"}[task.domain.lower()]
            with tempfile.TemporaryDirectory(prefix="workagent-office-eval-") as temp_dir:
                reopen_path = Path(temp_dir) / f"artifact{suffix}"
                shutil.copyfile(path, reopen_path)
                report = inspect_office_file(reopen_path, task)
            failures.extend(report.failures)
            warnings.extend(report.warnings)
            evidence.extend(report.evidence)
            channel_status.update(report.channel_status)
            for name, value in report.dimensions.items():
                dimension_values.setdefault(name, []).append(float(value))
            evidence.append(f"office_check_status:{report.status}")

        dimensions = {name: min(values) for name, values in dimension_values.items()}
        if not artifacts:
            dimensions.setdefault("format_validity", 0.0)
            dimensions.setdefault("marker_correctness", 0.0)
        evidence.extend([f"trace:{trace_id}", f"evaluator_version:{self.VERSION}", f"evaluator_hash:{self.evaluator_hash()}"])
        passed = not failures
        return EvaluationReport(
            passed=passed,
            score=1.0 if passed else 0.0,
            critical_failures=failures,
            warnings=warnings,
            dimensions=dimensions,
            evidence=evidence,
            channel_status=channel_status,
        )
