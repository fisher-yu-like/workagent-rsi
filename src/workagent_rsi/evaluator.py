"""Public evaluation delegates to the task-level LLM judge."""

from pathlib import Path
from .artifact_assessment import assessment_identity
from .office_checks import MEDIA_TYPES


class OfficeArtifactEvaluator:
    VERSION = "llm-task-review-v1"
    MEDIA_TYPES = MEDIA_TYPES

    def __init__(self, *, assessment_profile=None, report_root=None, assessment=None):
        self.report_root = Path(
            report_root or "project_artifacts/results/office-review"
        )
        self.assessment = assessment

    @classmethod
    def evaluator_hash(cls):
        return assessment_identity()

    def evaluate(self, task, artifacts, trace_id):
        from uuid import uuid4
        from .harness_artifact_evaluator import HarnessArtifactEvaluator

        return HarnessArtifactEvaluator(
            self.report_root / uuid4().hex, assessment=self.assessment
        ).evaluate(task, artifacts, trace_id)


class BasicEvaluator(OfficeArtifactEvaluator):
    """Compatibility name;there is no keyword-based acceptance fallback."""
