import importlib.util
import json
from pathlib import Path

import pytest

from workagent_rsi.hashing import sha256_file


def test_literal_report_keeps_quotes_and_multiline_observations_citable():
    path=Path('project_artifacts/phase3_experiments/scripts/prepare_natural_recovery.py')
    spec=importlib.util.spec_from_file_location('recovery_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    observed='Some numeric cells display "###".\nThe formula is =IF(A1,"NA",0).'
    report={'status':'PARTIAL','completion':0.5,'observed':observed,
            'observations':[{'observation':'Retain "Total" row','source_citations':[]}]}
    text=module.literal_report(report)
    assert observed in text
    assert 'Retain "Total" row' in text
    assert 'report.observations[0].observation' in text


def test_recovery_selects_only_missing_channels_and_preserves_successes(tmp_path,monkeypatch):
    from datetime import datetime,timezone
    from test_natural_judge import module as original_module,prepared_fixture
    from workagent_rsi.run_contracts import LiveCallPolicy
    from workagent_rsi.semantic_assessment import SemanticJudgement
    import workagent_rsi.model_judgement as provider_module
    original=original_module();public,evidence,render=prepared_fixture(tmp_path)
    prepared=tmp_path/'original';plan=original.prepare(public,evidence,render,prepared)
    base={'status':'PASS','completion':1,'observed':'Numbers display "###" in authored test only','confidence':None,'observations':[]}
    rows=[{**call,'decision':dict(base),'attempted':True} for call in plan['calls']]
    for index in [2,3,5]:rows[index]['decision']=None
    rows[5]['attempted']=False
    results=tmp_path/'original-results.json';results.write_text(json.dumps({'manifest_hash':plan['manifest_hash'],'rows':rows}),encoding='utf-8')
    path=Path('project_artifacts/phase3_experiments/scripts/prepare_natural_recovery.py')
    spec=importlib.util.spec_from_file_location('recovery_execution_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    recovered=tmp_path/'recovery';proposal=module.prepare(prepared,results,recovered)
    assert proposal['max_new_calls']==3
    assert [c['call_id'] for c in proposal['calls']]==[rows[i]['call_id'] for i in [2,3,5]]
    approval=tmp_path/'approval';approval.mkdir()
    state={'calls':[{'index':n,'status':'completed'} for n in range(59)],'reserved_wall_seconds':100}
    old=tmp_path/'old-state.json';old.write_text(json.dumps(state),encoding='utf-8')
    policy=LiveCallPolicy(allow_live_calls=True,approved_by_user=True,provider='codex-cli',model='gpt-6.1-sol',
        max_model_calls=62,max_tool_calls=0,max_wall_seconds=5400,approved_at=datetime.now(timezone.utc),approval_source='authored test substitute')
    p=approval/'live-policy.json';p.write_text(policy.model_dump_json(),encoding='utf-8')
    state['policy_sha256']=sha256_file(p);(approval/'budget-state.json').write_text(json.dumps(state),encoding='utf-8')
    (approval/'approval-receipt.json').write_text(json.dumps({'approved_by_user':True,'manifest_sha256':sha256_file(recovered/'proposal.json'),'policy_sha256':sha256_file(p),'historical_budget_path':str(old),'historical_budget_sha256':sha256_file(old)}),encoding='utf-8')
    class FakeProvider:
        def __init__(self,*args,**kwargs):pass
        def judge(self,request,work):
            data={**base,'observations':[{'evidence_id':i['evidence_id'],'quote':i['text'][:10],
                'observation':'Authored test check','source_citations':[]} for i in request['evidence']['items']]}
            if request['phase']=='consistency':assert '\\"###\\"' not in '\n'.join(i['text'] for i in request['evidence']['items'])
            return SemanticJudgement.model_validate(data),{'status':'completed','model_calls':1}
    monkeypatch.setattr(provider_module,'ModelJudgementProvider',FakeProvider)
    output=tmp_path/'actual';module.execute(recovered,p,output)
    final=json.loads((output/'results.json').read_text(encoding='utf-8'))
    assert len(final['rows'])==3 and len(final['effective_rows'])==60
    assert final['effective_rows'][0]['decision']==rows[0]['decision']
    assert all(row['decision'] is not None for row in final['effective_rows'])
    assert not final['quality_qualified']
    partial=tmp_path/'partial.json';partial.write_text(json.dumps({'manifest_hash':plan['manifest_hash'],'rows':rows[:10]}),encoding='utf-8')
    with pytest.raises(ValueError,match='finish all unissued'):module.prepare(prepared,partial,tmp_path/'not-ready')
    combined=module.prepare(prepared,partial,tmp_path/'combined',allow_unissued=True,max_total_seconds=7200)
    assert combined['max_new_calls']==53 and combined['original_processed_slots']==10
    assert combined['unissued_slots']==50 and combined['original_valid_decisions']==7
    assert combined['max_total_seconds']==7200 and not combined['allow_live_calls']
