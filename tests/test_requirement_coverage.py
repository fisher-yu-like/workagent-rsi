"""Independent task obligations; no output-derived requirement oracle."""
from copy import deepcopy

from openpyxl import Workbook
import pytest

from workagent_rsi.artifact_assessment import assess, spec_from_task
from workagent_rsi.assessment_contracts import AcceptanceSpec, Location, Requirement
from workagent_rsi.contracts import TaskSpec


def task():
    return TaskSpec(task_id='coverage', domain='excel', instruction='Write 42 in Sheet!A1. Add a chart.')


def base_spec():
    return AcceptanceSpec(task_id='coverage', version='test-v1', artifacts={'output':'excel'},
        dimension_weights={'content':1}, requirements=[
            Requirement(requirement_id='answer', description='Write the input-derived answer',
                check='excel.cell', location=Location(artifact='output',sheet='Sheet',cell='A1'),
                expected=42, critical=True, dimension='content', evidence_source='authored task oracle')])


def inventory(spec=None):
    from workagent_rsi.requirement_coverage import task_fingerprint, spec_coverage_fingerprint
    return {'task_id':'coverage', 'reviewed':True, 'provenance':{
        'kind':'human_review', 'reviewer':'authored-test-reviewer', 'review_ref':'authored-review-v1',
        'task_hash':task_fingerprint(task()), 'spec_hash':spec_coverage_fingerprint(spec or base_spec())},
        'requirements':[{'requirement_id':'write', 'source_quote':'Write 42 in Sheet!A1.',
            'source_ref':'task.instruction','obligation':'Write the required value',
            'validation_method':'deterministic','check_ids':['answer']},
            {'requirement_id':'chart','source_quote':'Add a chart.', 'source_ref':'task.instruction',
             'obligation':'Add the chart','validation_method':'uncovered','check_ids':[]}]}


def validate(inv, *, profile='task_acceptance', spec=None, current_task=None):
    from workagent_rsi.requirement_coverage import validate_spec_coverage
    return validate_spec_coverage(current_task or task(), inv, spec or base_spec(), evaluation_profile=profile)


def write_book(tmp_path):
    path=tmp_path/'book.xlsx'; book=Workbook(); book.active['A1']=42; book.save(path);book.close()
    return path


def test_blank_analysis_is_spec_incomplete_even_when_readable(tmp_path):
    t=TaskSpec(task_id='analysis',domain='excel',instruction='Aggregate all sales by region and add a chart.')
    spec=spec_from_task(t)
    shared,score,_=assess(spec,{'output':write_book(tmp_path)})
    assert shared.spec_admission.status=='SPEC_INCOMPLETE'
    assert score.task_score is None and score.acceptance_status!='PASS'


def test_structural_only_has_no_task_score_or_task_success(tmp_path):
    payload=base_spec().model_dump();payload['evaluation_profile']='structural_only'
    spec=AcceptanceSpec.model_validate(payload)
    _,score,_=assess(spec,{'output':write_book(tmp_path)})
    assert score.task_score is None and score.task_acceptance=='NOT_ASSESSED'
    assert score.total_score is None
    assert score.check_score==100


def test_missing_mandatory_chart_cannot_be_hidden_by_perfect_checks():
    report=validate(inventory())
    assert report.status=='SPEC_INCOMPLETE'
    assert report.requirement_coverage.ratio==0.5
    assert report.uncovered_requirement_ids==['chart']


def test_reviewed_complete_inventory_admits_task_score(tmp_path):
    from workagent_rsi.requirement_coverage import task_fingerprint
    spec=base_spec(); inv=inventory(spec);inv['requirements']=inv['requirements'][:1]
    current=task().model_copy(update={'instruction':'Write 42 in Sheet!A1.'})
    inv['provenance']['task_hash']=task_fingerprint(current)
    payload=spec.model_dump();payload.update(evaluation_profile='task_acceptance',
        task_context=current.model_dump(mode='json'),requirement_inventory=inv)
    _,score,_=assess(AcceptanceSpec.model_validate(payload),{'output':write_book(tmp_path)})
    assert score.task_score==100 and score.task_acceptance=='PASS'
    assert score.requirement_coverage.ratio==1 and score.coverage.ratio==1


@pytest.mark.parametrize('change', ['missing_check','unreviewed','model_self_review','wrong_quote','wrong_task','wrong_spec','empty_inventory'])
def test_invalid_coverage_cannot_admit_research(change):
    inv=inventory();inv['requirements']=inv['requirements'][:1]
    if change=='missing_check': inv['requirements'][0]['check_ids']=['does-not-exist']
    if change=='unreviewed':inv['reviewed']=False
    if change=='model_self_review':inv['provenance']['kind']='model_generated'
    if change=='wrong_quote':inv['requirements'][0]['source_quote']='Invented obligation'
    if change=='wrong_task':inv['provenance']['task_hash']='a'*64
    if change=='wrong_spec':inv['provenance']['spec_hash']='b'*64
    if change=='empty_inventory':inv['requirements']=[]
    assert validate(inv,profile='research').status=='SPEC_INCOMPLETE'


def test_legacy_explicit_spec_is_not_reviewed_task_acceptance(tmp_path):
    _,score,_=assess(base_spec(),{'output':write_book(tmp_path)})
    assert score.spec_admission.status=='LEGACY_UNREVIEWED'
    assert score.task_score is None and score.task_acceptance=='NOT_ASSESSED'
    assert 'declared' in score.scope_note.lower()


def test_inapplicable_check_does_not_cover_mandatory_requirement():
    spec=base_spec(); r=spec.requirements[0]
    # Keep a scoring check so this is a valid spec with a non-applicable mapped check.
    payload=spec.model_dump();payload['requirements'].append({**r.model_dump(),'requirement_id':'unused','applicable':False,'weight':0})
    spec=AcceptanceSpec.model_validate(payload);inv=inventory(spec);inv['requirements']=inv['requirements'][:1]
    inv['requirements'][0]['check_ids']=['unused']
    assert validate(inv,spec=spec).status=='SPEC_INCOMPLETE'


def test_changed_task_cannot_reuse_review():
    inv=inventory();inv['requirements']=inv['requirements'][:1]
    other=task().model_copy(update={'instruction':'Write 99 in Sheet!A1.'})
    assert validate(inv,current_task=other).status=='SPEC_INCOMPLETE'


def test_unknown_source_reference_is_not_task_provenance():
    inv=inventory(); inv['requirements']=inv['requirements'][:1]
    inv['requirements'][0]['source_ref']='output.xlsx'
    assert validate(inv).status=='SPEC_INCOMPLETE'


def test_coverage_validation_is_read_only():
    inv=inventory();before=deepcopy(inv);spec=base_spec();spec_before=spec.model_dump()
    validate(inv,spec=spec)
    assert inv==before and spec.model_dump()==spec_before


def test_nested_spec_cannot_replace_actual_task_context():
    spec=base_spec();inv=inventory();inv['requirements']=inv['requirements'][:1]
    payload=spec.model_dump();payload.update(evaluation_profile='research',
        requirement_inventory=inv,task_context=task().model_dump(mode='json'))
    changed=task().model_copy(update={'instruction':'Write 99 instead.',
        'expected_constraints':{'acceptance_spec':payload}})
    bound=spec_from_task(changed)
    assert bound.task_context['instruction']=='Write 99 instead.'
    assert validate(inv,spec=bound,current_task=changed).status=='SPEC_INCOMPLETE'


@pytest.mark.parametrize('problem',['duplicate_obligation','wrong_method','no_reviewer','empty_review_ref'])
def test_invalid_review_or_mapping(problem):
    inv=inventory();inv['requirements']=inv['requirements'][:1]
    if problem=='duplicate_obligation': inv['requirements']*=2
    if problem=='wrong_method':inv['requirements'][0]['validation_method']='visual'
    if problem=='no_reviewer':inv['provenance'].pop('reviewer')
    if problem=='empty_review_ref':inv['provenance']['review_ref']=''
    assert validate(inv).status=='SPEC_INCOMPLETE'


def test_authorized_frozen_input_quote_can_ground_requirement(tmp_path):
    from workagent_rsi.requirement_coverage import task_fingerprint,spec_coverage_fingerprint
    from workagent_rsi.hashing import sha256_file
    source=tmp_path/'authorized.txt';source.write_text('Required value: 42',encoding='utf-8')
    t=task().model_copy(update={'input_files':(str(source),),'instruction':'Write 42 in Sheet!A1.'})
    payload=base_spec().model_dump();payload['input_hashes']={str(source):sha256_file(source)}
    spec=AcceptanceSpec.model_validate(payload);inv=inventory(spec);inv['requirements']=inv['requirements'][:1]
    inv['requirements'][0].update(source_ref='input:0',source_quote='Required value: 42')
    inv['provenance'].update(task_hash=task_fingerprint(t),spec_hash=spec_coverage_fingerprint(spec))
    assert validate(inv,current_task=t,spec=spec).status=='PASS'
    source.write_text('Required value: 99',encoding='utf-8')
    assert validate(inv,current_task=t,spec=spec).status=='SPEC_INCOMPLETE'


def test_perfect_check_completion_does_not_imply_requirement_coverage(tmp_path):
    payload=base_spec().model_dump();payload.update(evaluation_profile='task_acceptance',
        task_context=task().model_dump(mode='json'),requirement_inventory=inventory())
    _,score,_=assess(AcceptanceSpec.model_validate(payload),{'output':write_book(tmp_path)})
    assert score.coverage.ratio==1 and score.requirement_coverage.ratio==0.5
    assert score.check_score==100 and score.task_score is None and score.total_score is None
