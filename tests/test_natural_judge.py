import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image

from workagent_rsi.hashing import sha256_file,canonical_json_hash


def module():
    path=Path('project_artifacts/phase3_experiments/scripts/natural_judge.py')
    spec=importlib.util.spec_from_file_location('natural_judge_test',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


def test_page_batches_cover_every_page_with_connected_overlap():
    mod=module()
    for count in [1,7,8,9,15,48,96]:
        pages=list(range(1,count+1));groups=mod.page_batches(pages)
        assert set(p for g in groups for p in g)==set(pages)
        assert all(1<=len(g)<=8 for g in groups)
        assert all(set(a)&set(b) for a,b in zip(groups,groups[1:]))


def test_aggregation_does_not_promote_partial_missing_or_contradictory_results():
    mod=module();passed={'status':'PASS'}
    assert mod.aggregate([passed,{'status':'PARTIAL'}])=='FAIL'
    assert mod.aggregate([passed,None])=='INCOMPLETE'
    assert mod.aggregate([{'status':'FAIL'},None])=='FAIL'
    assert mod.aggregate([passed,{'status':'NEEDS_REVIEW'}])=='INCOMPLETE'
    assert mod.aggregate([passed,passed])=='PASS'


def prepared_fixture(tmp_path):
    public=tmp_path/'public';evidence=tmp_path/'evidence'
    public.mkdir();evidence.mkdir();rows=[];files=[];pages=[]
    for n in range(20):
        cid=f'case-{n}';artifact=public/(cid+'.docx');artifact.write_bytes(b'authored text observations only')
        source=public/(cid+'.txt');source.write_text('Original public facts',encoding='utf-8')
        page=public/(cid+'.png');Image.new('RGB',(10,10),'white').save(page)
        observations=[]
        for index,path in enumerate([artifact,source]):
            name=f'{cid}-{index}.json';obj={'file':str(path),'text_partition_complete':True,'limitations':[],
                'partition':{'partitions':[{'items':[{'location':{'artifact':'output' if index==0 else 'input-1'},'text':'Original public facts'}]}]}}
            (evidence/name).write_text(json.dumps(obj),encoding='utf-8')
            observations.append({'file':path.name,'source_sha256':sha256_file(path),'evidence':name,
                'evidence_sha256':sha256_file(evidence/name),'parser_warnings':[]})
        rows.append({'case_id':cid,'domain':'word','cohort':'natural-blind','artifact':artifact.name,
            'artifact_hash':sha256_file(artifact),'instruction':'Preserve supplied facts.','inputs':[source.name]})
        files.append({'case_id':cid,'files':observations})
        pages.append({'case_id':cid,'status':'available','pages':[{'page':1,'file':page.name,'sha256':sha256_file(page)}]})
    (public/'review-manifest.json').write_text(json.dumps({'cases':rows}),encoding='utf-8')
    (public/'rendered-pages.json').write_text(json.dumps(pages),encoding='utf-8')
    (evidence/'report.json').write_text(json.dumps({'cases':files}),encoding='utf-8')
    # Poison files must never enter model inputs.
    (public/'human-labels.json').write_text('PRIVATE_HUMAN_LABELS',encoding='utf-8')
    (public/'reference-answer.json').write_text('PRIVATE_REFERENCE_ANSWER',encoding='utf-8')
    recovery=tmp_path/'recovery.json';recovery.write_text('[]',encoding='utf-8')
    return public,evidence,recovery


def test_frozen_requests_bind_every_actual_page_and_exclude_private_files(tmp_path):
    mod=module();public,evidence,recovery=prepared_fixture(tmp_path)
    output=tmp_path/'prepared';plan=mod.prepare(public,evidence,recovery,output)
    assert len(plan['calls'])==60 and plan['max_tool_calls']==0 and not plan['allow_live_calls']
    assert plan['manifest_hash']==canonical_json_hash({k:v for k,v in plan.items() if k!='manifest_hash'})
    for call in plan['calls']:
        assert sha256_file(output/call['request'])==call['sha256']
        text=(output/call['request']).read_text(encoding='utf-8')
        assert 'PRIVATE_HUMAN_LABELS' not in text and 'PRIVATE_REFERENCE_ANSWER' not in text
    consistency=[c for c in plan['calls'] if c['phase']=='consistency']
    assert len(consistency)==20 and all(len(c['parents'])==2 for c in consistency)
    with pytest.raises(FileExistsError):mod.prepare(public,evidence,recovery,output)


def test_modified_artifact_rejected_before_live_provider(tmp_path):
    mod=module();public,evidence,recovery=prepared_fixture(tmp_path)
    (public/'case-0.docx').write_bytes(b'changed')
    with pytest.raises(ValueError,match='artifact changed'):mod.prepare(public,evidence,recovery,tmp_path/'rejected')


def test_chinese_output_requires_font_qualified_pages_before_any_model_call(tmp_path):
    mod=module();public,evidence,recovery=prepared_fixture(tmp_path)
    file=evidence/'case-0-0.json';data=json.loads(file.read_text(encoding='utf-8'))
    data['partition']['partitions'][0]['items'][0]['text']='中文标题'
    file.write_text(json.dumps(data),encoding='utf-8')
    manifest=json.loads((evidence/'report.json').read_text(encoding='utf-8'))
    manifest['cases'][0]['files'][0]['evidence_sha256']=sha256_file(file)
    (evidence/'report.json').write_text(json.dumps(manifest),encoding='utf-8')
    with pytest.raises(ValueError,match='qualified Chinese-font render'):
        mod.prepare(public,evidence,recovery,tmp_path/'rejected')


@pytest.mark.parametrize('fail_at',[None,5])
@pytest.mark.parametrize('historical',[0,1])
def test_execution_keeps_failed_requests_and_frozen_parent_dependencies(tmp_path,monkeypatch,fail_at,historical):
    from datetime import datetime,timezone
    from workagent_rsi.run_contracts import LiveCallPolicy
    from workagent_rsi.semantic_assessment import SemanticJudgement
    from workagent_rsi.judgement_provider import VisualJudgement
    mod=module();public,evidence,recovery=prepared_fixture(tmp_path)
    prepared=tmp_path/'prepared';plan=mod.prepare(public,evidence,recovery,prepared)
    approved=tmp_path/'approved';approved.mkdir()
    policy=LiveCallPolicy(allow_live_calls=True,approved_by_user=True,provider='codex-cli',
        model='gpt-6.1-sol',max_model_calls=60+historical,max_tool_calls=0,max_wall_seconds=5400,
        approved_at=datetime(2026,10,28,tzinfo=timezone.utc),approval_source='authored fake-provider fixture')
    path=approved/'live-policy.json';path.write_text(policy.model_dump_json(),encoding='utf-8')
    receipt={'approved_by_user':True,'manifest_sha256':sha256_file(prepared/'manifest.json'),'policy_sha256':sha256_file(path)}
    if historical:
        state={'calls':[{'index':1,'status':'completed','exit_code':0}],'reserved_wall_seconds':59}
        old=tmp_path/'old-budget.json';old.write_text(json.dumps(state),encoding='utf-8')
        receipt.update(historical_attempts=1,historical_budget_path=str(old),historical_budget_sha256=sha256_file(old))
        state['policy_sha256']=sha256_file(path)
        (approved/'budget-state.json').write_text(json.dumps(state),encoding='utf-8')
    (approved/'approval-receipt.json').write_text(json.dumps(receipt),encoding='utf-8')
    issued=[]
    class FakeProvider:
        def __init__(self,*args,**kwargs):pass
        def identity_config(self):return {'provider':'authored-test-substitute'}
        def judge(self,request,output):
            issued.append(request)
            if fail_at==len(issued):return None,{'status':'error','model_calls':1}
            base={'status':'PASS','completion':1,'observed':'Authored provider substitute, not real evidence','confidence':None}
            if request['modality']=='semantic':
                base['observations']=[{'evidence_id':i['evidence_id'],'quote':i['text'][:20],
                    'observation':'Fixture check','source_citations':[]} for i in request['evidence']['items']]
                return SemanticJudgement.model_validate(base),{'status':'completed','model_calls':1}
            base['observations']=[{'image_id':i['image_id'],'artifact_location':i['artifact_location'],
                'region':'fixture','observation':'Fixture check'} for i in request['images']]
            return VisualJudgement.model_validate(base),{'status':'completed','model_calls':1}
    monkeypatch.setattr(mod,'ModelJudgementProvider',FakeProvider)
    output=tmp_path/'actual';mod.execute(prepared,path,output)
    result=json.loads((output/'results.json').read_text(encoding='utf-8'))
    assert len(result['rows'])==(fail_at or 60)
    assert not result['quality_qualified']
    if fail_at:
        assert result['rows'][-1]['decision'] is None
        assert 'INCOMPLETE' in result['declared_scope_results'].values()
    else:
        assert issued[2]['phase']=='consistency'
        assert {i['evidence_id'] for i in issued[2]['evidence']['items']}==set(plan['calls'][2]['parents'])
