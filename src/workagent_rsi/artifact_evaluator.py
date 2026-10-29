"""Adapt the model's decision to the public report;do not rescore it."""

from .assessment_contracts import Coverage, ScoreReport
from .run_contracts import AssessmentOutcome, AssessmentCoverage


class ArtifactEvaluator:
    VERSION = "llm-task-review-v1"

    def evaluate(self, assessment):
        decision = assessment.judgement
        status = decision.status if decision else "INCOMPLETE"
        quality = (
            decision.completion * 100
            if decision and decision.completion is not None
            else None
        )
        return ScoreReport(
            task_id=assessment.spec.task_id,
            spec_hash=assessment.spec_hash,
            evaluator_identity=assessment.evaluator_identity,
            artifact_hashes=assessment.artifact_hashes,
            acceptance_status=status,
            total_score=quality,
            dimension_scores={},
            task_acceptance=status,
            task_score=quality,
            quality_score=quality,
            check_score=None,
            coverage=Coverage(applicable=0, completed=0, ratio=0, status_counts={}),
            criterion_results=[],
            evidence_refs=decision.evidence_ids if decision else [],
            scope_note="Task reasonableness,completion and score are model judgements;no coded task rubric.",
            score_semantics="llm-task-review-v1",
        )


def outcome_from_score(score):
    status = {
        "PASS": "pass",
        "PARTIAL": "partial",
        "FAIL": "fail",
        "NEEDS_REVIEW": "incomplete",
        "INCOMPLETE": "incomplete",
    }[score.task_acceptance]
    quality = None if score.quality_score is None else score.quality_score / 100
    return AssessmentOutcome(
        status=status,
        score=quality,
        quality_score=quality,
        task_acceptance=score.task_acceptance,
        coverage=AssessmentCoverage(),
        failure_origin="artifact_defect"
        if status in {"fail", "partial"}
        else "assessment_gap"
        if status == "incomplete"
        else None,
        report_refs=score.evidence_refs,
    )
