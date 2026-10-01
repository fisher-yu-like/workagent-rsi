"""Score a shared, evidence-bound assessment without re-reading artifacts."""

from collections import Counter

from .assessment_contracts import Assessment, Coverage, ScoreReport


class ArtifactEvaluator:
    VERSION = "office-artifact-evaluator-v1"

    def evaluate(self, assessment: Assessment) -> ScoreReport:
        # Revalidate nested containers even if a caller mutated a frozen model's dict.
        assessment = Assessment.model_validate(assessment.model_dump(mode="json"))
        spec = assessment.spec
        checks = {c.requirement_id: c for c in assessment.checks}
        dimensions = {}
        for dimension in spec.dimension_weights:
            reqs = [r for r in spec.requirements if r.dimension == dimension and r.applicable and r.weight > 0]
            dimensions[dimension] = (
                None if any(checks[r.requirement_id].completion is None for r in reqs)
                else round(100 * sum(r.weight * checks[r.requirement_id].completion for r in reqs) / sum(r.weight for r in reqs), 6)
            )
        total = None if any(s is None for s in dimensions.values()) else round(sum(dimensions[d] * w for d, w in spec.dimension_weights.items()), 6)
        critical = [checks[r.requirement_id] for r in spec.requirements if r.critical and r.applicable]
        if any(c.completion is not None and c.completion < 1 for c in critical):
            status = "FAIL"
        elif total is None or any(c.completion is None for c in critical):
            status = "INCOMPLETE"
        else:
            status = "PASS" if total >= spec.quality_threshold else "FAIL"
        counts = Counter(c.status for c in assessment.checks)
        applicable = len(assessment.checks) - counts["NOT_APPLICABLE"]
        completed = sum(counts[s] for s in ("PASS", "PARTIAL", "FAIL"))
        return ScoreReport(
            task_id=spec.task_id, spec_hash=assessment.spec_hash,
            evaluator_identity=assessment.evaluator_identity, artifact_hashes=assessment.artifact_hashes,
            acceptance_status=status, total_score=total, dimension_scores=dimensions,
            coverage=Coverage(applicable=applicable, completed=completed, ratio=completed / applicable if applicable else 0, status_counts=dict(counts)),
            criterion_results=assessment.checks, evidence_refs=[e.evidence_id for e in assessment.evidence], scope_note=spec.scope_note,
        )
