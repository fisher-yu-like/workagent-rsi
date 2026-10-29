"""Pass model-authored issues to repair;do not synthesize task rules."""

from .assessment_contracts import ArtifactIssue, IssueReport, RepairAction
from .hashing import canonical_json_hash


class ArtifactVerifier:
    VERSION = "llm-task-review-v1"

    def verify(self, assessment):
        issues = []
        for item in assessment.judgement.issues if assessment.judgement else []:
            identity = (
                item.issue_id
                or canonical_json_hash(
                    {
                        "task": assessment.spec.task_id,
                        "issue": item.model_dump(mode="json"),
                    }
                )[:24]
            )
            target = {
                "artifact_defect": "artifact",
                "spec_gap": "acceptance_spec",
                "assessment_gap": "assessment_capability",
            }[item.kind]
            issues.append(
                ArtifactIssue(
                    issue_id=identity,
                    requirement_id=identity,
                    kind=item.kind,
                    location=item.location,
                    observed=item.description,
                    expected=None,
                    evidence_refs=item.evidence_refs,
                    severity=item.severity,
                    repair_hint=item.repair_suggestion,
                    recheck_ids=[],
                    feedback_visibility="develop",
                    failure_origin=item.kind,
                    affected_requirements=[identity],
                    verification_steps=[
                        "Repeat model review against the original task."
                    ],
                    repair_action=RepairAction(
                        target=target,
                        description=item.repair_suggestion or item.description,
                        locations=[item.location] if target == "artifact" else [],
                        evidence_refs=item.evidence_refs,
                    ),
                )
            )
        return IssueReport(
            task_id=assessment.spec.task_id,
            spec_hash=assessment.spec_hash,
            evaluator_identity=assessment.evaluator_identity,
            artifact_hashes=assessment.artifact_hashes,
            issues=issues,
        )
