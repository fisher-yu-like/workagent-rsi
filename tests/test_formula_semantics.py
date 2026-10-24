import importlib
from pathlib import Path

from openpyxl import Workbook
import pytest

from workagent_rsi.artifact_assessment import assess,SharedAssessment
from workagent_rsi.assessment_contracts import AcceptanceSpec,Requirement,Location
from workagent_rsi.hashing import sha256_file


def book(tmp_path,value='=B2+B3'):
    path=tmp_path/'input.xlsx';b=Workbook();b.active['B2']=4;b.active['B3']=6;b.active['B4']=value;b.save(path);b.close();return path


def specification(check='excel.formula',expected='=SUM(B2:B3)',**options):
    return AcceptanceSpec(task_id='formula',version='authored-v1',artifacts={'output':'excel'},dimension_weights={'content':1},requirements=[Requirement(
        requirement_id='sum',description='Sum supplied input rows',check=check,expected=expected,options=options,
        location=Location(artifact='output',sheet='Sheet',cell='B4'),critical=True,dimension='content',evidence_source='independent arithmetic')])


def test_equivalent_expression_without_engine_is_gap_not_string_failure(tmp_path):
    shared,score,_=assess(specification(formula_policy='equivalent',oracle_value=10,input_variants=[
        {'name':'negative','inputs':{'Sheet!B2':-3,'Sheet!B3':9},'expected_value':6}]),{'output':book(tmp_path)})
    assert shared.checks[0].status=='UNAVAILABLE' and score.total_score is None


def test_exact_formula_alias_still_rejects_other_expression(tmp_path):
    assert assess(specification('excel.formula_exact'),{'output':book(tmp_path)})[0].checks[0].status=='FAIL'


def test_formula_present_distinguishes_literal_from_expression(tmp_path):
    assert assess(specification('excel.formula_present',True),{'output':book(tmp_path,25)})[0].checks[0].status=='FAIL'


def test_formula_present_accepts_expression_without_claiming_recalculation(tmp_path):
    shared,_,_=assess(specification('excel.formula_present',True),{'output':book(tmp_path)})
    assert shared.checks[0].status=='PASS'


def test_stale_cache_is_not_recalculation_evidence(tmp_path):
    shared,score,_=assess(specification('excel.recalculated_value',10),{'output':book(tmp_path)})
    assert shared.checks[0].status=='UNAVAILABLE' and score.total_score is None


def test_hardcoded_value_cannot_satisfy_equivalent_formula(tmp_path):
    shared,_,_=assess(specification(formula_policy='equivalent',oracle_value=25,input_variants=[
        {'name':'changed','inputs':{'Sheet!B2':-1},'expected_value':5}]),{'output':book(tmp_path,25)})
    assert shared.checks[0].status=='FAIL'


def test_unconfigured_engine_does_not_start_host_process(tmp_path,monkeypatch):
    from workagent_rsi.spreadsheet_recalc import RecalculationEngine
    import subprocess
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:pytest.fail('no host process'))
    source=book(tmp_path);before=sha256_file(source);output=tmp_path/'new.xlsx'
    result=RecalculationEngine().recalculate(source,output)
    assert result.status=='unavailable' and not output.exists()
    assert sha256_file(source)==before and result.qualification=='unverified'


def test_engine_refuses_overwriting_output_or_source(tmp_path):
    from workagent_rsi.spreadsheet_recalc import RecalculationEngine
    source=book(tmp_path)
    with pytest.raises((ValueError,FileExistsError)):RecalculationEngine().recalculate(source,source)


@pytest.mark.parametrize('formula',['=WEBSERVICE("https://example.invalid")','=SUM([1]Sheet1!B2)','=NOW()'])
def test_external_or_dynamic_formula_requires_explicit_gap(tmp_path,formula):
    from workagent_rsi.spreadsheet_recalc import RecalculationEngine
    result=RecalculationEngine().recalculate(book(tmp_path,formula),tmp_path/'out.xlsx')
    assert result.status=='unavailable' and 'external' in result.error.lower() or result.status=='unavailable' and 'dynamic' in result.error.lower()


def test_equivalence_needs_independent_oracle_and_input_variants(tmp_path):
    shared,_,_=assess(specification(formula_policy='equivalent'),{'output':book(tmp_path)})
    assert shared.checks[0].failure_origin=='spec_gap'


@pytest.mark.parametrize('variant',[{'name':'bad','inputs':{},'expected_value':0},
    {'name':'bad','inputs':{'Sheet!B4':99},'expected_value':99},
    {'name':'bad','inputs':{'B2':1},'expected_value':1},
    {'name':'bad','inputs':{'Sheet!B2':1},'expected_value':float('nan')}])
def test_invalid_variant_is_spec_gap(tmp_path,variant):
    shared,_,_=assess(specification(formula_policy='equivalent',oracle_value=10,input_variants=[variant]),{'output':book(tmp_path)})
    assert shared.checks[0].failure_origin=='spec_gap'


def test_unit_fixture_result_cannot_qualify_real_recalculation(tmp_path):
    from workagent_rsi.spreadsheet_recalc import RecalcResult
    from workagent_rsi.artifact_evaluator import ArtifactEvaluator
    class AuthoredEngine:
        output_root=tmp_path/'cases'
        def identity_config(self):return {'qualification':'unit_fixture'}
        def recalculate(self,source,output):return RecalcResult(status='available',source_sha256=sha256_file(source),
            values={'Sheet!B4':10},qualification='unit_fixture',engine_identity='authored arithmetic only')
    path=book(tmp_path);engine=SharedAssessment(recalculation=AuthoredEngine())
    shared=engine.inspect(specification('excel.recalculated_value',10),{'output':path})
    assert shared.checks[0].status=='UNAVAILABLE' and ArtifactEvaluator().evaluate(shared).total_score is None


class AuthoredSandbox:
    def __init__(self,problem=None):
        from types import SimpleNamespace
        self.problem=problem;self.calls=0
        self.policy=SimpleNamespace(backend='apptainer-ssh',network='none',remote_image_sha256='a'*64,
            model_dump=lambda **kw:{'backend':'apptainer-ssh','network':'none','runtime':'authored unit fixture'})
    def run(self,script,root,timeout):
        import json,shutil
        from workagent_rsi.run_contracts import ExecutionOutcome
        self.calls+=1;(root/'outputs').mkdir();shutil.copyfile(root/'inputs/source.xlsx',root/'outputs/recalculated.xlsx')
        config=json.loads((root/'inputs/recalc-policy.json').read_text())
        meta={'status':'available','source_sha256':config['source_sha256'],'worker_sha256':config['worker_sha256'],
            'output_sha256':sha256_file(root/'outputs/recalculated.xlsx'),'calculate_all':True,
            'load_policy':{'ReadOnly':True,'MacroExecutionMode':0,'UpdateDocMode':0},'owned_cleanup':True,
            'environment':{'office_version':'AUTHORED PROTOCOL FIXTURE, not an Office run','office_binary_sha256':'b'*64}}
        if self.problem=='source':meta['source_sha256']='0'*64
        if self.problem=='output':meta['output_sha256']='0'*64
        if self.problem=='cleanup':meta['owned_cleanup']=False
        (root/'outputs/recalc-metadata.json').write_text(json.dumps(meta))
        (root/'trace.json').write_text(json.dumps({'qualification':'unit_fixture','cleanup':{'confirmed_absent':True},
            'resource_observations':{'passed':False},'capability':{'image_sha256':'a'*64}}))
        return ExecutionOutcome(status='succeeded',trace_refs=['trace.json'])


def test_isolated_protocol_uses_copy_and_retains_unit_qualification(tmp_path):
    from workagent_rsi.spreadsheet_recalc import RecalculationEngine
    sandbox=AuthoredSandbox();source=book(tmp_path);before=sha256_file(source)
    result=RecalculationEngine(sandbox=sandbox,qualification='unit_fixture').recalculate(source,tmp_path/'out.xlsx')
    assert result.status=='available' and result.qualification=='unit_fixture'
    assert sandbox.calls==1 and sha256_file(source)==before
    assert 'Sheet!B4' not in result.values # Fixture never fabricates a formula cache.


@pytest.mark.parametrize('problem',['source','output','cleanup'])
def test_bad_worker_receipt_cannot_become_recalculation_evidence(tmp_path,problem):
    from workagent_rsi.spreadsheet_recalc import RecalculationEngine
    result=RecalculationEngine(sandbox=AuthoredSandbox(problem),qualification='unit_fixture').recalculate(book(tmp_path),tmp_path/'out.xlsx')
    assert result.status=='error' and not (tmp_path/'out.xlsx').exists()


def test_unit_runtime_trace_cannot_be_marked_isolated_qualification(tmp_path):
    from workagent_rsi.spreadsheet_recalc import RecalculationEngine
    result=RecalculationEngine(sandbox=AuthoredSandbox(),qualification='isolated_run').recalculate(book(tmp_path),tmp_path/'out.xlsx')
    assert result.status=='error' and 'proof' in result.error


def test_exact_check_cannot_be_relaxed_by_equivalent_option(tmp_path):
    shared,_,_=assess(specification('excel.formula_exact',formula_policy='equivalent',oracle_value=10,input_variants=[
        {'name':'zero','inputs':{'Sheet!B2':0},'expected_value':6}]),{'output':book(tmp_path)})
    assert shared.checks[0].failure_origin=='spec_gap'
