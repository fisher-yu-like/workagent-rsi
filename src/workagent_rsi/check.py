"""Simple names for validation, evaluation and acceptance."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .contracts import ArtifactRef, EvaluationReport, TaskSpec
from .evaluator import BasicEvaluator, OfficeArtifactEvaluator
from .frozen_evaluator import FrozenEvaluator, ResponseJudge
from .promotion import PromotionController
from .rsi_contracts import CandidatePatch, EvaluationContract, PromotionDecision, VerificationReport
from .skill_runtime import PilotSkillConfig
from .verifier import CandidateVerifier, VerificationPolicy


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
    ) -> None:
        self.verifier = verifier or CandidateVerifier()
        self.promotion = promotion or PromotionController()
        self.evaluator = evaluator or BasicEvaluator()
        self.office_evaluator = office_evaluator or OfficeArtifactEvaluator()
        self.frozen = frozen

    def verify(
        self,
        candidate: CandidatePatch,
        workspace: str | Path,
        policy: VerificationPolicy,
    ) -> VerificationReport:
        return self.verifier.verify(candidate, workspace, policy)

    def evaluate(
        self,
        task: TaskSpec,
        artifacts: Sequence[ArtifactRef],
        trace_id: str,
        *,
        office: bool | None = None,
    ) -> EvaluationReport:
        use_office = office if office is not None else task.domain.lower() in {"excel", "word", "powerpoint"}
        evaluator = self.office_evaluator if use_office else self.evaluator
        return evaluator.evaluate(task, artifacts, trace_id)

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


__all__ = [
    "BasicEvaluator",
    "CandidateVerifier",
    "Check",
    "FrozenEvaluator",
    "OfficeArtifactEvaluator",
    "PromotionController",
    "ResponseJudge",
    "VerificationPolicy",
]
