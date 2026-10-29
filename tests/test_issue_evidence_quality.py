"""Executable defect facts and capability gaps from one frozen assessment."""

from openpyxl import Workbook
import pytest

from workagent_rsi.artifact_assessment import spec_from_task
from workagent_rsi.assessment_contracts import Location, RSIFeedback, ArtifactIssue
from workagent_rsi.contracts import TaskSpec
from workagent_rsi.rsi_feedback import candidate_feedback


def specification():
    return spec_from_task(
        TaskSpec(task_id="issues", domain="excel", instruction="Review the workbook.")
    )


def assess(spec, artifacts):
    from test_llm_task_review import Provider, judgement
    from workagent_rsi.artifact_assessment import assess as review

    issue = {
        "issue_id": "total",
        "description": "Authored model problem",
        "location": {"artifact": "output", "sheet": "Sheet", "cell": "A1"},
        "kind": "artifact_defect",
        "severity": "major",
        "repair_suggestion": "Model-authored suggestion",
        "evidence_refs": ["output"],
    }
    return review(spec, artifacts, provider=Provider(judgement("FAIL", 0.2, [issue])))


def workbook(tmp_path):
    path=tmp_path/'book.xlsx';book=Workbook();book.active['A1']=7;book.save(path);book.close();return path


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
