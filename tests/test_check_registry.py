"""Preflight truth comes from authored invalid specs, before any artifact read."""
import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from workagent_rsi.artifact_assessment import SharedAssessment, assess, spec_from_task
from workagent_rsi.assessment_contracts import AcceptanceSpec, Location, Requirement
from workagent_rsi.contracts import TaskSpec


def spec(check='excel.cell', expected=42, domain='excel', **location):
    return AcceptanceSpec(task_id='preflight',version='authored-v1',artifacts={'output':domain},
        dimension_weights={'content':1},requirements=[Requirement(requirement_id='required',
            description='Authored requirement',check=check,expected=expected,
            location=Location(artifact='output',**location),critical=True,
            dimension='content',evidence_source='independent preflight fixture')])


def preflight(value, capabilities=None):
    from workagent_rsi.check_registry import validate_acceptance_spec
    return validate_acceptance_spec(value, capabilities or {})


@pytest.mark.parametrize('problem', ['no_sheet','no_cell','invalid_cell','backwards_range','beyond_excel_limit',
    'unknown_check','wrong_domain','empty_expected','wrong_expected_type','missing_slide','missing_object',
    'missing_table_column','invalid_weight','nonfinite_expected','bad_pages','bad_fact_location'])
def test_invalid_spec_is_spec_gap(problem):
    value=spec(sheet='Sheet',cell='A1').model_dump(mode='json')
    r=value['requirements'][0]
    if problem=='no_sheet':r['location'].pop('sheet')
    if problem=='no_cell':r['location'].pop('cell')
    if problem=='invalid_cell':r['location']['cell']='!'
    if problem=='backwards_range':r.update(check='excel.range',expected=[[1]]);r['location']['cell']='B5:A1'
    if problem=='beyond_excel_limit':r['location']['cell']='XFE1'
    if problem=='unknown_check':r['check']='invented.check'
    if problem=='wrong_domain':value['artifacts']['output']='word'
    if problem=='empty_expected':r.update(check='excel.sheets',expected=[])
    if problem=='wrong_expected_type':r.update(check='excel.formula',expected=42)
    if problem=='missing_slide':r.update(check='powerpoint.bounds',expected=[]);r['location']={'artifact':'output'};value['artifacts']['output']='powerpoint'
    if problem=='missing_object':r.update(check='powerpoint.object_text',expected='text');r['location']={'artifact':'output','slide':1};value['artifacts']['output']='powerpoint'
    if problem=='missing_table_column':r.update(check='word.table_cell',expected='text');r['location']={'artifact':'output','table':1,'row':1};value['artifacts']['output']='word'
    if problem=='invalid_weight':r['weight']=-1
    if problem=='nonfinite_expected':r['expected']=float('nan')
    if problem=='bad_pages':r.update(check='visual',options={'pages':[True]})
    if problem=='bad_fact_location':r.update(check='facts.consistent',options={'locations':[{'artifact':'output','cell':'A1'}]})
    report=preflight(value)
    assert report.status=='SPEC_INCOMPLETE'
    assert any(f.origin=='spec_gap' for f in report.findings)


def test_missing_renderer_is_capability_gap_not_bad_artifact():
    report=preflight(spec('visual',None,domain='powerpoint',slide=1),{'visual_judge':True})
    assert report.status=='ASSESSMENT_INCOMPLETE'
    assert {f.origin for f in report.findings}=={'assessment_gap'}
    assert 'renderer' in ' '.join(f.message for f in report.findings)


def test_unknown_check_is_rejected_before_document_parser(tmp_path,monkeypatch):
    import docx
    calls=[]
    def forbidden(*args,**kwargs):calls.append(args);raise AssertionError('parser must not run')
    path=tmp_path/'invalid.docx';path.write_bytes(b'not an Office package')
    monkeypatch.setattr(docx,'Document',forbidden)
    shared,score,issues=assess(spec('invented',True,domain='word'),{'output':path})
    assert calls==[]
    assert shared.checks[0].failure_origin=='spec_gap'
    assert shared.checks[0].completion is None
    assert issues.issues[0].kind=='spec_gap'
    assert score.total_score is None


def test_legacy_constraints_each_have_adapter_record():
    t=TaskSpec(task_id='legacy',domain='excel',instruction='authored task',expected_constraints={
        'required_text':'TOKEN','marker':'TOKEN','required_cells':{'Sheet!A1':42},'unsupported_layout_rule':True})
    converted=spec_from_task(t)
    rows={r.key:r for r in converted.legacy_adapter_records}
    assert set(rows)==set(t.expected_constraints)
    assert rows['marker'].status=='alias'
    assert rows['unsupported_layout_rule'].status=='unsupported'
    assert rows['unsupported_layout_rule'].reason
    assert any(r.check=='unsupported.unsupported_layout_rule' for r in converted.requirements)


def test_valid_check_still_runs_with_invalid_sibling(tmp_path):
    value=spec(sheet='Sheet',cell='A1').model_dump()
    value['requirements'].append({**value['requirements'][0],'requirement_id':'unknown','check':'unknown'})
    path=tmp_path/'book.xlsx';book=Workbook();book.active['A1']=42;book.save(path)
    shared,score,issues=assess(AcceptanceSpec.model_validate(value),{'output':path})
    assert [c.status for c in shared.checks]==['PASS','UNAVAILABLE']
    assert shared.checks[1].failure_origin=='spec_gap'
    assert score.total_score is None and issues.issues[0].kind=='spec_gap'


def test_nonapplicable_unknown_check_keeps_explicit_reason():
    value=spec(sheet='Sheet',cell='A1').model_dump()
    value['requirements'].append({**value['requirements'][0],'requirement_id':'not-required','check':'unknown','applicable':False,'weight':0})
    assert preflight(value).status=='PASS'


def test_registry_is_single_source_for_generated_support_document():
    from workagent_rsi.check_registry import registry_manifest,render_registry_markdown
    rows=registry_manifest()
    assert 'excel.cell' in rows and 'visual' in rows
    assert rows['excel.cell']['required_location_fields']==['sheet','cell']
    assert Path('docs/check_registry.md').read_text(encoding='utf-8')==render_registry_markdown()


def test_capability_claim_is_explicit_true_not_truthy_text():
    report=preflight(spec('visual',None,domain='powerpoint'),{'renderer':'false','visual_judge':'yes'})
    assert report.status=='ASSESSMENT_INCOMPLETE'


def test_malformed_legacy_map_remains_visible():
    t=TaskSpec(task_id='legacy',domain='excel',instruction='check data',expected_constraints={'required_cells':['A1']})
    converted=spec_from_task(t)
    assert converted.legacy_adapter_records[0].status=='unsupported'
    assert preflight(converted).status=='SPEC_INCOMPLETE'


def test_explicit_spec_wrapper_does_not_drop_extra_constraints():
    original=spec(sheet='Sheet',cell='A1')
    t=TaskSpec(task_id='preflight',domain='excel',instruction='Read data',
        expected_constraints={'acceptance_spec':original.model_dump(mode='json'),'extra_business_rule':'must retain'})
    bound=spec_from_task(t)
    assert {r.key for r in bound.legacy_adapter_records}==set(t.expected_constraints)
    assert preflight(bound).status=='SPEC_INCOMPLETE'


@pytest.mark.parametrize('field,value',[('slide',True),('object_id',1.5),('critical','true')])
def test_location_and_critical_types_are_not_coerced(field,value):
    payload=spec(sheet='Sheet',cell='A1').model_dump(mode='json')
    r=payload['requirements'][0]
    if field=='critical':r[field]=value
    else:r['location'][field]=value
    assert preflight(payload).status=='SPEC_INCOMPLETE'


@pytest.mark.parametrize('field',['weight','dimension_weight'])
def test_boolean_weights_are_not_numeric_configuration(field):
    payload=spec(sheet='Sheet',cell='A1').model_dump(mode='json')
    if field=='weight':payload['requirements'][0]['weight']=True
    else:payload['dimension_weights']['content']=True
    assert preflight(payload).status=='SPEC_INCOMPLETE'
