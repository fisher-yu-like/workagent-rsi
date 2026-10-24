"""Executable defect facts and capability gaps from one frozen assessment."""
import json

from openpyxl import Workbook
import pytest

from workagent_rsi.artifact_assessment import SharedAssessment,assess,spec_from_task
from workagent_rsi.artifact_verifier import ArtifactVerifier
from workagent_rsi.assessment_contracts import AcceptanceSpec,Location,Requirement,RSIFeedback,ArtifactIssue
from workagent_rsi.contracts import TaskSpec
from workagent_rsi.hashing import sha256_file
from workagent_rsi.rsi_feedback import candidate_feedback,build_feedback


def specification(check='excel.cell',**changes):
    req=Requirement(requirement_id='total',description='Required total',check=check,
        location=Location(artifact='output',sheet='Sheet',cell='A1') if check.startswith('excel.') else Location(artifact='output'),
        expected=42 if check=='excel.cell' else 'readable',critical=True,dimension='content',
        evidence_source='authored independent expected total',**changes)
    return AcceptanceSpec(task_id='issues',version='authored-v1',artifacts={'output':'excel'},
        dimension_weights={'content':1},requirements=[req])


def workbook(tmp_path):
    path=tmp_path/'book.xlsx';book=Workbook();book.active['A1']=7;book.save(path);book.close();return path


def test_wrong_total_issue_has_actual_expected_location_and_action(tmp_path):
    shared,score,report=assess(specification(),{'output':workbook(tmp_path)})
    issue=report.issues[0]
    assert (issue.observed,issue.expected,issue.requested_location.cell)==(7,42,'A1')
    assert issue.observed_locations[0].cell=='A1' and issue.failure_origin=='artifact_defect'
    assert issue.affected_requirements==['total'] and issue.repair_action.target=='artifact'
    assert issue.repair_action.locations==[issue.requested_location]
    assert issue.verification_steps and any('total' in step for step in issue.verification_steps)
    assert issue.repair_action.evidence_refs==issue.evidence_refs
    gaps=assess(specification('visual'),{'output':tmp_path/'book.xlsx'})[2]
    (tmp_path/'issue-report-v2-examples.json').write_text(json.dumps({'defect':report.model_dump(mode='json'),
        'assessment_gap':gaps.model_dump(mode='json')},indent=2))


@pytest.mark.parametrize('check',['visual','semantic'])
def test_assessment_gap_action_targets_capability_not_document(tmp_path,check):
    issue=assess(specification(check),{'output':workbook(tmp_path)})[2].issues[0]
    assert issue.kind==issue.failure_origin=='assessment_gap'
    assert issue.repair_action.target=='assessment_capability'
    assert issue.repair_action.locations==[] and issue.skill_improvement_hint is None
    assert 'delete' not in issue.repair_action.description.lower()


def test_invalid_spec_action_targets_spec_not_artifact(tmp_path):
    issue=assess(specification('unsupported.check'),{'output':workbook(tmp_path)})[2].issues[0]
    assert issue.kind==issue.failure_origin=='spec_gap'
    assert issue.repair_action.target=='acceptance_spec' and issue.repair_action.locations==[]


def test_no_issue_fabricates_causal_certainty(tmp_path):
    issue=assess(specification(),{'output':workbook(tmp_path)})[2].issues[0]
    assert issue.cause_hypothesis is None and issue.failure_origin=='artifact_defect'
    assert 'because' not in issue.repair_action.description.lower()


def test_feedback_does_not_contain_internal_answer_knob(tmp_path):
    spec=specification(repair_hint='Set sales_rows=all',skill_improvement_hint='sales_rows=all')
    shared,score,report=assess(spec,{'output':workbook(tmp_path)})
    issue=report.issues[0]
    assert issue.skill_improvement_hint is None and not issue.qualification_only
    feedback=build_feedback({'split':'develop','rows':[{'task_id':spec.task_id,'score_report':score.model_dump(mode='json'),
        'issue_report':report.model_dump(mode='json')}]})
    text=feedback.model_dump_json()
    assert 'sales_rows' not in text
    assert feedback.tasks[0]['issues'][0]['repair_action']['target']=='artifact'


def test_qualification_hint_requires_explicit_flag(tmp_path):
    spec=specification(skill_improvement_hint='sales_rows=all',options={'qualification_only':True})
    issue=assess(spec,{'output':workbook(tmp_path)})[2].issues[0]
    assert issue.qualification_only is True and issue.skill_improvement_hint=='sales_rows=all'


def test_stable_issue_id_does_not_depend_on_unrelated_check(tmp_path):
    path=workbook(tmp_path);spec=specification();first=assess(spec,{'output':path})[2].issues[0]
    payload=spec.model_dump(mode='json')
    payload['requirements'].append(Requirement(requirement_id='format',description='Readable',check='file.readable',
        expected=True,location=Location(artifact='output'),dimension='content',evidence_source='OOXML parser').model_dump(mode='json'))
    second=assess(AcceptanceSpec.model_validate(payload),{'output':path})[2].issues[0]
    assert first.issue_id==second.issue_id


def test_grouping_by_requirement_does_not_claim_shared_cause(tmp_path):
    spec=specification(skill_improvement_hint='shared generic advice')
    extra=spec.requirements[0].model_copy(update={'requirement_id':'another','expected':100})
    spec=spec.model_copy(update={'requirements':[*spec.requirements,extra]})
    _,score,report=assess(spec,{'output':workbook(tmp_path)})
    feedback=build_feedback({'split':'develop','rows':[{'task_id':spec.task_id,'score_report':score.model_dump(mode='json'),
        'issue_report':report.model_dump(mode='json')}]})
    assert set(feedback.issue_groups)=={'total','another'}
    assert all(i.cause_hypothesis is None for i in report.issues)


def test_admission_gap_is_actionable_even_when_declared_checks_pass(tmp_path):
    task=TaskSpec(task_id='issues',domain='excel',instruction='Analyze all sales and add a chart.')
    _,_,report=assess(spec_from_task(task),{'output':workbook(tmp_path)})
    assert any(i.kind=='spec_gap' and i.repair_action.target=='acceptance_spec' for i in report.issues)
    assert all(i.kind!='artifact_defect' for i in report.issues)


def test_verifier_reuses_snapshot_even_when_file_changes_later(tmp_path):
    path=workbook(tmp_path);digest=sha256_file(path);shared=SharedAssessment().inspect(specification(),{'output':path})
    book=Workbook();book.active['A1']=42;book.save(path);book.close()
    report=ArtifactVerifier().verify(shared)
    assert report.artifact_hashes['output']==digest and report.issues[0].observed==7
    assert report.issues[0].repair_action.evidence_refs==shared.checks[0].evidence_refs


def test_new_advice_fields_do_not_bypass_feedback_visibility(tmp_path):
    _,_,report=assess(specification(),{'output':workbook(tmp_path)})
    issue=report.issues[0].model_dump(mode='json')
    issue['repair_action']={'target':'artifact','description':'Correct the value','credentials':'PRIVATE_TOKEN',
        'locations':[{'artifact':'output','cell':'A1','path':'PRIVATE_PATH'}],'evidence_refs':issue['evidence_refs']}
    issue['qualification_only']=False;issue['skill_improvement_hint']='sales_rows=all'
    feedback=candidate_feedback(RSIFeedback(tasks=[{'task_id':'issues','issues':[issue]}]))
    text=feedback.model_dump_json()
    assert 'PRIVATE_TOKEN' not in text and 'PRIVATE_PATH' not in text and 'sales_rows' not in text
    assert feedback.tasks[0]['issues'][0]['repair_action']['description']=='Correct the value'


def test_legacy_issue_records_remain_readable_without_inventing_action():
    issue=ArtifactIssue(issue_id='old',requirement_id='old',kind='artifact_defect',location=Location(artifact='output'),
        evidence_refs=['old-evidence'],severity='minor',repair_hint='Historical hint',recheck_ids=['old'],feedback_visibility='develop')
    assert issue.repair_action is None and issue.failure_origin is None and issue.verification_steps==[]


def test_protected_and_gap_issues_do_not_enter_develop_repair_feedback(tmp_path):
    _,_,report=assess(specification(),{'output':workbook(tmp_path)})
    issue=report.issues[0].model_dump(mode='json')
    hidden={**issue,'feedback_visibility':'evaluation_only','observed':'PRIVATE_EXPECTED'}
    gap={**issue,'kind':'assessment_gap','repair_hint':'PRIVATE_CAPABILITY'}
    feedback=candidate_feedback(RSIFeedback(tasks=[{'task_id':'issues','issues':[hidden,gap]}]))
    assert feedback.tasks[0]['issues']==[] and 'PRIVATE_' not in feedback.model_dump_json()


def test_clean_historical_feedback_projection_is_idempotent():
    from test_candidate_context import feedback
    original=feedback()
    assert candidate_feedback(original)==original
    assert candidate_feedback(candidate_feedback(original))==original


@pytest.mark.parametrize('change',['target','evidence'])
def test_action_cannot_change_failure_origin_or_evidence(tmp_path,change):
    issue=assess(specification(),{'output':workbook(tmp_path)})[2].issues[0]
    payload=issue.model_dump(mode='json')
    if change=='target':
        payload['repair_action'].update(target='assessment_capability',locations=[])
    else:
        payload['repair_action']['evidence_refs']=['invented-evidence']
    with pytest.raises(ValueError):ArtifactIssue.model_validate(payload)


def test_unobserved_check_cannot_become_artifact_edit_from_legacy_origin_tag(tmp_path):
    from workagent_rsi.assessment_contracts import Assessment
    shared=SharedAssessment().inspect(specification('visual'),{'output':workbook(tmp_path)})
    payload=shared.model_dump(mode='json');payload['checks'][0]['failure_origin']='artifact_defect'
    report=ArtifactVerifier().verify(Assessment.model_validate(payload))
    assert report.issues[0].kind=='assessment_gap'
    assert report.issues[0].repair_action.target=='assessment_capability'
    assert report.issues[0].repair_action.locations==[]
