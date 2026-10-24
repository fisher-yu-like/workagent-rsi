"""Locate defects and assessment gaps; never edit artifacts or candidate skills."""

from .assessment_contracts import ArtifactIssue, Assessment, IssueReport
from .hashing import canonical_json_hash


class ArtifactVerifier:
    VERSION = "office-artifact-verifier-v1"

    def verify(self, assessment: Assessment) -> IssueReport:
        assessment = Assessment.model_validate(assessment.model_dump(mode="json"))
        requirements = {r.requirement_id: r for r in assessment.spec.requirements}
        issues = []
        for check in assessment.checks:
            if check.status in {"PASS", "NOT_APPLICABLE"}:
                continue
            r = requirements[check.requirement_id]
            gap = check.completion is None
            issues.append(ArtifactIssue(
                issue_id=canonical_json_hash({"task": assessment.spec.task_id, "spec": assessment.spec_hash, "requirement": r.requirement_id})[:24],
                requirement_id=r.requirement_id, kind=(check.failure_origin or 'assessment_gap') if gap else "artifact_defect",
                location=(check.observed_locations[0] if check.observed_locations else check.location), observed=check.observed, expected=check.expected,
                requested_location=check.requested_location or check.location,observed_locations=check.observed_locations,
                evidence_refs=check.evidence_refs, severity="advisory" if gap else ("blocking" if r.critical else "minor"),
                cause_hypothesis=None,
                repair_hint=(('Correct the frozen acceptance specification: ' if check.failure_origin=='spec_gap' else 'Restore assessment capability or review the evidence: ') + check.message) if gap else r.repair_hint,
                skill_improvement_hint=None if gap else r.skill_improvement_hint,
                recheck_ids=[r.requirement_id], feedback_visibility=r.feedback_visibility,
            ))
        return IssueReport(task_id=assessment.spec.task_id, spec_hash=assessment.spec_hash,
                           evaluator_identity=assessment.evaluator_identity, artifact_hashes=assessment.artifact_hashes, issues=issues)
