"""Locate defects and assessment gaps; never edit artifacts or candidate skills."""

from .assessment_contracts import ArtifactIssue, Assessment, IssueReport, RepairAction
from .artifact_feedback import repair_description
from .hashing import canonical_json_hash


class ArtifactVerifier:
    VERSION = "office-artifact-verifier-v2"

    def verify(self, assessment: Assessment) -> IssueReport:
        assessment = Assessment.model_validate(assessment.model_dump(mode="json"))
        requirements = {r.requirement_id: r for r in assessment.spec.requirements}
        issues = []
        for check in assessment.checks:
            if check.status in {"PASS", "NOT_APPLICABLE"}:
                continue
            r = requirements[check.requirement_id]
            gap = check.completion is None
            # Missing observations cannot establish an artifact defect, even if
            # a historical caller supplied an inconsistent origin annotation.
            kind=('spec_gap' if check.failure_origin=='spec_gap' else 'assessment_gap') if gap else 'artifact_defect'
            requested=check.requested_location or check.location
            locations=[requested]
            for location in check.observed_locations:
                if location not in locations:
                    locations.append(location)
            if kind=='spec_gap':
                target='acceptance_spec'
                description='Have the task owner correct the frozen specification or check configuration, then repeat admission.'
            elif kind=='assessment_gap':
                target='assessment_capability'
                description=('Obtain the required rendered evidence and qualified visual review before deciding on content changes.'
                    if r.check in {'visual','powerpoint.overlap','powerpoint.bounds'} else
                    'Restore the required assessment capability, authorized sources or evidence coverage and rerun this check.')
            else:
                target='artifact';description=repair_description(r.check)
            action=RepairAction(target=target,description=description,
                locations=locations if target=='artifact' else [],evidence_refs=check.evidence_refs)
            steps=[f'Rerun {r.requirement_id} ({r.check}) with the same frozen specification and authorized input hashes.',
                   'Compare the new observation with the independent expected value and retain the new evidence.',
                   'Recheck every mandatory criterion and any preservation requirements before accepting the revised artifact.']
            qualification=r.options.get('qualification_only') is True
            issues.append(ArtifactIssue(
                issue_id=canonical_json_hash({'task':assessment.spec.task_id,'requirement':r.requirement_id,
                    'check':r.check,'requested_location':requested.model_dump(mode='json')})[:24],
                requirement_id=r.requirement_id, kind=kind,
                location=(check.observed_locations[0] if check.observed_locations else check.location), observed=check.observed, expected=check.expected,
                requested_location=check.requested_location or check.location,observed_locations=check.observed_locations,
                evidence_refs=check.evidence_refs, severity="advisory" if gap else ("blocking" if r.critical else "minor"),
                cause_hypothesis=None,
                repair_hint=description,
                skill_improvement_hint=r.skill_improvement_hint if qualification and not gap else None,
                recheck_ids=[r.requirement_id], feedback_visibility=r.feedback_visibility,
                failure_origin=kind,affected_requirements=[r.requirement_id],repair_action=action,
                verification_steps=steps,qualification_only=qualification,
                impact='Blocks task acceptance for this critical requirement.' if r.critical and not gap else
                    'Leaves assessment incomplete; artifact correctness is unknown.' if gap else
                    f'Reduces fulfillment of the declared {r.dimension} requirement.',
            ))
        admission=assessment.spec_admission
        if admission is not None and admission.status in {'SPEC_INCOMPLETE','ASSESSMENT_INCOMPLETE'}:
            kind='spec_gap' if admission.status=='SPEC_INCOMPLETE' else 'assessment_gap'
            refs=['spec-admission:'+canonical_json_hash(admission.model_dump(mode='json'))]
            requested=next(iter(assessment.spec.requirements)).location
            description='Have the task owner review mandatory obligations, check mappings and frozen task/input/spec bindings.'
            action=RepairAction(target='acceptance_spec' if kind=='spec_gap' else 'assessment_capability',
                description=description,evidence_refs=refs)
            issues.append(ArtifactIssue(issue_id=canonical_json_hash({'task':assessment.spec.task_id,'kind':'spec_admission'})[:24],
                requirement_id='spec_admission',kind=kind,failure_origin=kind,location=requested,requested_location=requested,
                observed=admission.model_dump(mode='json'),expected='Complete independently reviewed task requirement admission',
                evidence_refs=refs,severity='advisory',repair_hint=description,repair_action=action,
                affected_requirements=admission.uncovered_requirement_ids or list(requirements),
                verification_steps=['Repeat task/spec coverage admission with an independent review receipt.',
                    'Rerun every required check with the frozen task, authorized inputs and reviewed specification.'],
                recheck_ids=list(requirements),feedback_visibility='evaluation_only',
                impact='Whole-task acceptance is unavailable despite any passing declared checks.'))
        return IssueReport(task_id=assessment.spec.task_id, spec_hash=assessment.spec_hash,
                           evaluator_identity=assessment.evaluator_identity, artifact_hashes=assessment.artifact_hashes, issues=issues)
