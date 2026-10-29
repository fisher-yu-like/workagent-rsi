"""Simple names for validation, evaluation and acceptance."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

from .contracts import ArtifactRef, EvaluationReport, TaskSpec
from .evaluator import BasicEvaluator, OfficeArtifactEvaluator
from .frozen_evaluator import FrozenEvaluator, ResponseJudge
from .promotion import PromotionController
from .rsi_contracts import CandidatePatch, EvaluationContract, PromotionDecision, VerificationReport
from .skill_runtime import PilotSkillConfig
from .verifier import CandidateVerifier, VerificationPolicy
from .artifact_assessment import SharedAssessment
from .artifact_evaluator import ArtifactEvaluator
from .artifact_verifier import ArtifactVerifier
from .assessment_contracts import AcceptanceSpec, IssueReport, ScoreReport
from .task_review import TaskReviewSpec


class Check:
    """Group the checks a caller normally needs without merging trust roles."""

    def __init__(
        self,
        *,
        verifier: CandidateVerifier | None = None,
        promotion: PromotionController | None = None,
        evaluator: BasicEvaluator | None = None,
        office_evaluator: OfficeArtifactEvaluator | None = None,
        frozen: FrozenEvaluator | None = None,
        artifact_assessment: SharedAssessment | None = None,
        report_root: str | Path | None = None,
        assessment_profile: str | None = None,
    ) -> None:
        self.verifier = verifier or CandidateVerifier()
        self.promotion = promotion or PromotionController()
        self.artifact_assessment = artifact_assessment or SharedAssessment()
        self.evaluator = evaluator or BasicEvaluator(assessment=self.artifact_assessment)
        self.office_evaluator = office_evaluator or OfficeArtifactEvaluator(assessment=self.artifact_assessment)
        self.frozen = frozen
        self.report_root=Path(report_root) if report_root is not None else Path.cwd()/'project_artifacts/results/check'
        self.assessment_profile=assessment_profile

    def verify(
        self,
        candidate: CandidatePatch,
        workspace: str | Path,
        policy: VerificationPolicy,
        **validation_context,
    ) -> VerificationReport:
        return self.verifier.verify(candidate, workspace, policy, **validation_context)

    def evaluate(
        self,
        task: TaskSpec,
        artifacts: Sequence[ArtifactRef],
        trace_id: str,
        *,
        office: bool | None = None,
        assessment_profile: str | None = None,
    ) -> EvaluationReport:
        office_domain=task.domain.lower() in {'excel','word','powerpoint'}
        if office_domain and office is False:
            raise ValueError('Office tasks require the versioned LLM review chain')
        if office_domain or office:
            from .harness_artifact_evaluator import HarnessArtifactEvaluator
            return HarnessArtifactEvaluator(self.report_root/uuid4().hex,assessment=self.artifact_assessment).evaluate(task,artifacts,trace_id)
        return self.evaluator.evaluate(task,artifacts,trace_id)

    def evaluate_split(
        self,
        tasks: Sequence[TaskSpec],
        split_name: str,
        config: PilotSkillConfig,
        contract: EvaluationContract,
        result_root: str | Path,
        *,
        reveal_per_task: bool = True,
    ) -> dict:
        if self.frozen is None:
            raise ValueError("a FrozenEvaluator is required for split evaluation")
        return self.frozen.evaluate_split(
            tasks,
            split_name,
            config,
            contract,
            result_root,
            reveal_per_task=reveal_per_task,
        )

    def promote(
        self,
        candidate_id: str,
        verification: VerificationReport,
        metrics: dict[str, float | int | bool],
        contract: EvaluationContract,
    ) -> PromotionDecision:
        return self.promotion.decide(candidate_id, verification, metrics, contract)

    decide = promote

    def assess_artifact(self, spec: TaskReviewSpec, artifacts: dict[str, str | Path]) -> tuple[ScoreReport, IssueReport]:
        """Call both fixed artifact skills over one shared evidence snapshot."""
        shared = self.artifact_assessment.inspect(spec, artifacts)
        return ArtifactEvaluator().evaluate(shared), ArtifactVerifier().verify(shared)

    def evaluate_artifact(self, spec: TaskReviewSpec, artifacts: dict[str, str | Path]) -> ScoreReport:
        return self.assess_artifact(spec, artifacts)[0]

    def verify_artifact(self, spec: TaskReviewSpec, artifacts: dict[str, str | Path]) -> IssueReport:
        return self.assess_artifact(spec, artifacts)[1]


__all__ = [
    "BasicEvaluator",
    "CandidateVerifier",
    "Check",
    "FrozenEvaluator",
    "OfficeArtifactEvaluator",
    "PromotionController",
    "ResponseJudge",
    "VerificationPolicy",
    "AcceptanceSpec",
    "ArtifactEvaluator",
    "ArtifactVerifier",
    "SharedAssessment",
]
