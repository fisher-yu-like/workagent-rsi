"""Versioned public assessment parity, using independently authored OOXML."""
import json
from pathlib import Path

from docx import Document
from openpyxl import Workbook
import pytest

from workagent_rsi.artifact_assessment import SharedAssessment,assess,spec_from_task
from workagent_rsi.assessment_contracts import AcceptanceSpec,Location,Requirement
from workagent_rsi.check import Check
from workagent_rsi.contracts import ArtifactRef,TaskSpec
from workagent_rsi.harness_artifact_evaluator import HarnessArtifactEvaluator
from workagent_rsi.hashing import sha256_file,canonical_json_hash


def authored_spec(*,visual=False,critical_weight=1):
    reqs=[Requirement(requirement_id='answer',description='Write the exact required value',check='excel.cell',
        location=Location(artifact='output',sheet='Sheet',cell='A1'),expected=42,critical=True,
        weight=critical_weight,dimension='content',evidence_source='authored task oracle')]
    if critical_weight==0:
        reqs.append(Requirement(requirement_id='readable',description='Readable',check='file.readable',
            location=Location(artifact='output'),expected=True,dimension='content',evidence_source='OOXML parser'))
    if visual:
        reqs.append(Requirement(requirement_id='visual',description='Readable layout',check='visual',
            location=Location(artifact='output'),critical=True,dimension='content',evidence_source='actual render'))
    return AcceptanceSpec(task_id='parity',version='authored-v1',artifacts={'output':'excel'},
        requirements=reqs,dimension_weights={'content':1})


def reviewed_task(spec):
    from workagent_rsi.requirement_coverage import task_context,task_fingerprint,spec_coverage_fingerprint
    instruction='Write 42 in Sheet!A1.'+(' Make the layout readable.' if any(r.check=='visual' for r in spec.requirements) else '')
    task=TaskSpec(task_id=spec.task_id,domain='excel',instruction=instruction)
    inv={'task_id':task.task_id,'reviewed':True,'provenance':{'kind':'human_review','reviewer':'authored-test-oracle',
        'review_ref':'authored-parity-review','task_hash':task_fingerprint(task),'spec_hash':spec_coverage_fingerprint(spec)},
        'requirements':[{'requirement_id':r.requirement_id,'source_quote':instruction,'source_ref':'task.instruction',
            'obligation':r.description,'validation_method':'visual' if r.check=='visual' else 'deterministic',
            'check_ids':[r.requirement_id]} for r in spec.requirements]}
    spec=AcceptanceSpec.model_validate({**spec.model_dump(mode='json'),'evaluation_profile':'task_acceptance',
        'task_context':task_context(task),'requirement_inventory':inv})
    return task.model_copy(update={'expected_constraints':{'acceptance_spec':spec.model_dump(mode='json')}})


def book(tmp_path,value=42):
    path=tmp_path/'book.xlsx';wb=Workbook();wb.active['A1']=value;wb.save(path);wb.close()
    return path


def ref(path):
    return ArtifactRef(artifact_id='authored',path=str(path),sha256=sha256_file(path),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',size_bytes=path.stat().st_size)


@pytest.mark.parametrize('value,expected',[(42,'PASS'),(7,'FAIL')])
def test_check_and_harness_share_identity_score_and_task_acceptance(tmp_path,value,expected):
    task=reviewed_task(authored_spec());path=book(tmp_path,value);artifact=ref(path)
    check=Check(report_root=tmp_path/'check').evaluate(task,[artifact],'check')
    harness=HarnessArtifactEvaluator(tmp_path/'harness').evaluate(task,[artifact],'harness')
    assert check.assessment_identity==harness.assessment_identity
    assert check.task_acceptance==harness.task_acceptance==expected
    assert check.quality_score==harness.quality_score
    assert check.assessment_outcome.spec_admission==harness.assessment_outcome.spec_admission
    assert check.assessment_outcome.check_completion.ratio==1
    assert check.passed is (expected=='PASS')
    (tmp_path/'parity-matrix.json').write_text(json.dumps({'check':check.model_dump(mode='json'),
        'harness':harness.model_dump(mode='json')},indent=2))


def test_blank_readable_file_cannot_pass_default_check_entrypoint(tmp_path):
    task=TaskSpec(task_id='analysis',domain='excel',instruction='Analyze regional sales and chart them.')
    result=Check().evaluate(task,[ref(book(tmp_path))],'authored')
    assert result.passed is False and result.score is None
    assert result.task_acceptance=='INCOMPLETE'
    assert result.assessment_outcome.spec_admission.status=='SPEC_INCOMPLETE'


def test_unreviewed_declared_checks_are_not_default_task_success(tmp_path):
    task=TaskSpec(task_id='parity',domain='excel',instruction='Write 42 in Sheet!A1.',
        expected_constraints={'acceptance_spec':authored_spec().model_dump(mode='json')})
    result=HarnessArtifactEvaluator(tmp_path/'harness').evaluate(task,[ref(book(tmp_path))],'authored')
    assert not result.passed and result.score is None and result.task_acceptance=='INCOMPLETE'


def test_critical_zero_weight_failure_blocks_task_even_with_raw_quality_100(tmp_path):
    task=reviewed_task(authored_spec(critical_weight=0))
    shared,score,_=assess(spec_from_task(task),{'output':book(tmp_path,7)})
    assert score.task_acceptance=='FAIL' and score.task_score==100
    result=HarnessArtifactEvaluator(tmp_path/'harness').evaluate(task,[ref(tmp_path/'book.xlsx')],'authored')
    assert result.task_acceptance=='FAIL' and result.passed is False
    assert result.assessment_outcome.quality_score==1


def test_missing_channel_keeps_quality_null_and_known_failure(tmp_path):
    task=reviewed_task(authored_spec(visual=True))
    result=HarnessArtifactEvaluator(tmp_path/'harness').evaluate(task,[ref(book(tmp_path,7))],'authored')
    assert result.task_acceptance=='FAIL' and result.quality_score is None and result.passed is False
    assert result.assessment_outcome.status=='fail'
    assert result.assessment_outcome.check_completion.completed==1


def test_structural_only_is_not_assessed_as_whole_task(tmp_path):
    task=TaskSpec(task_id='parity',domain='excel',instruction='Analyze sales.',
        expected_constraints={'evaluation_profile':'structural_only'})
    result=Check(report_root=tmp_path/'check').evaluate(task,[ref(book(tmp_path))],'authored')
    assert result.task_acceptance=='NOT_ASSESSED' and result.quality_score is None and not result.passed


def test_legacy_requires_explicit_profile_and_remains_labelled(tmp_path):
    task=TaskSpec(task_id='parity',domain='excel',instruction='Write 42.',expected_constraints={'required_cells':{'Sheet!A1':42}})
    result=Check(report_root=tmp_path/'check').evaluate(task,[ref(book(tmp_path))],'authored',assessment_profile='legacy')
    assert result.passed and result.score==1 and result.score_semantics=='legacy'
    assert result.task_acceptance=='NOT_ASSESSED'


def test_office_evaluator_default_uses_the_versioned_chain(tmp_path):
    from workagent_rsi.evaluator import OfficeArtifactEvaluator
    task=reviewed_task(authored_spec());artifact=ref(book(tmp_path))
    result=OfficeArtifactEvaluator(report_root=tmp_path/'direct').evaluate(task,[artifact],'authored')
    common=HarnessArtifactEvaluator(tmp_path/'common').evaluate(task,[artifact],'authored')
    assert result.assessment_identity==common.assessment_identity and result.task_acceptance=='PASS'


def test_office_task_cannot_bypass_the_chain_via_basic_flag(tmp_path):
    task=TaskSpec(task_id='parity',domain='excel',instruction='Analyze sales.')
    with pytest.raises(ValueError):Check().evaluate(task,[ref(book(tmp_path))],'authored',office=False)


def test_same_task_bytes_via_check_harness_and_rsi(tmp_path,monkeypatch):
    from workagent_rsi.harness import Harness
    from workagent_rsi.workagent_evaluator import WorkAgentFrozenEvaluator
    from workagent_rsi.workagent_provider import WorkAgentConfig,WorkAgentSkill
    from workagent_rsi.rsi_contracts import EvaluationContract
    path=book(tmp_path);task=reviewed_task(authored_spec())
    class Adapter:
        def __init__(self,*a,**k):pass
        def execute(self,*a,**k):yield {'kind':'artifact','artifact_path':str(path),'media_type':ref(path).media_type}
    monkeypatch.setattr('workagent_rsi.run.WorkAgentOfficeAdapter',Adapter)
    cfg=WorkAgentConfig(verify_com=False)
    result=Harness(tmp_path/'harness',workagent_config=cfg).run(task)
    direct=Check(report_root=tmp_path/'check').evaluate(task,[ref(path)],'authored')
    evaluator=WorkAgentFrozenEvaluator(workagent_config=cfg,input_base=tmp_path,assessment_output_root=tmp_path/'judge')
    digest=canonical_json_hash([task.model_dump(mode='json')])
    contract=EvaluationContract(contract_id='parity',dataset_hash=digest,split_hashes={'develop':digest},
        evaluator_hash=evaluator.evaluator_hash,assessment_mode='artifact-v1',assessment_identity=evaluator.assessment_identity,
        acceptance_hashes={task.task_id:spec_from_task(task).fingerprint()},
        provider_policy='workagent-config:'+canonical_json_hash(cfg.model_dump(mode='json')),seeds=[1],repeats=1,
        timeout_seconds=10,thresholds={},git_commit='authored-unit-fixture')
    report=evaluator.evaluate_split([task],'develop',WorkAgentSkill(instructions="Use current authored input."),contract,tmp_path/'rsi',reveal_per_task=True)
    row=report['rows'][0]
    assert direct.assessment_identity==result['evaluation']['assessment_identity']==row['assessment_identity']
    assert direct.task_acceptance==result['evaluation']['task_acceptance']==row['task_acceptance']=='PASS'
    assert direct.quality_score==result['evaluation']['quality_score']==row['quality_score']==1
    (tmp_path/'parity-matrix.json').write_text(json.dumps({'check':direct.model_dump(mode='json'),
        'harness':result['evaluation'],'rsi':row},indent=2))


def test_default_harness_does_not_upgrade_unreviewed_checks_to_task_success(tmp_path):
    from workagent_rsi.harness import Harness
    task=TaskSpec(task_id='word',domain='word',instruction='Write REQUIRED.',expected_constraints={'required_text':'REQUIRED'})
    result=Harness(tmp_path/'runs',execution_provider='local_office').run(task)
    assert result['state']=='UNAVAILABLE' and result['evaluation']['score'] is None
    assert result['evaluation']['task_acceptance']=='INCOMPLETE'
    assert result['evaluation']['assessment_outcome']['check_completion']['ratio']==1


def test_hash_mismatch_is_an_assessment_gap_without_false_quality(tmp_path):
    task=reviewed_task(authored_spec());artifact=ref(book(tmp_path)).model_copy(update={'sha256':'0'*64})
    result=Check(report_root=tmp_path/'check').evaluate(task,[artifact],'authored')
    assert not result.passed and result.quality_score is None
    assert result.assessment_outcome.failure_origin=='assessment_gap'


def test_public_report_rejects_success_inconsistent_with_outcome(tmp_path):
    from workagent_rsi.contracts import EvaluationReport
    task=reviewed_task(authored_spec())
    result=HarnessArtifactEvaluator(tmp_path/'harness').evaluate(task,[ref(book(tmp_path,7))],'authored')
    payload=result.model_dump(mode='json');payload['passed']=True
    with pytest.raises(ValueError):EvaluationReport.model_validate(payload)


def test_legacy_adapter_preserves_versioned_outcome_and_historical_records(tmp_path):
    from workagent_rsi.run_contracts import assessment_from_legacy
    task=reviewed_task(authored_spec())
    result=HarnessArtifactEvaluator(tmp_path/'harness').evaluate(task,[ref(book(tmp_path))],'authored')
    assert assessment_from_legacy({'evaluation':result.model_dump(mode='json')})==result.assessment_outcome
    historical={'evaluation':{'passed':True,'score':1.0}};before=json.dumps(historical,sort_keys=True)
    assert assessment_from_legacy(historical).score==1
    assert json.dumps(historical,sort_keys=True)==before


def test_required_com_gap_does_not_leave_a_perfect_success_report(tmp_path,monkeypatch):
    from workagent_rsi.harness import Harness
    from workagent_rsi.workagent_provider import WorkAgentConfig
    from workagent_rsi.contracts import EvaluationReport
    task=reviewed_task(authored_spec());path=book(tmp_path)
    class Adapter:
        def __init__(self,*a,**k):pass
        def execute(self,*a,**k):yield {'kind':'artifact','artifact_path':str(path),'media_type':ref(path).media_type}
    monkeypatch.setattr('workagent_rsi.run.WorkAgentOfficeAdapter',Adapter)
    monkeypatch.setattr('workagent_rsi.run.verify_stored_office_artifacts',lambda *a:{
        'ok':False,'status':'unavailable','error':'authored COM capability gap; no Office call'})
    result=Harness(tmp_path/'harness',workagent_config=WorkAgentConfig(verify_com=True)).run(task)
    report=EvaluationReport.model_validate(result['evaluation'])
    assert result['state']=='UNAVAILABLE' and report.score is None and not report.passed
    assert report.task_acceptance=='INCOMPLETE' and report.quality_score is None
