import json

from openpyxl import Workbook
from PIL import Image
import pytest

from test_benchmark_blind_pack import load_script
from workagent_rsi.hashing import sha256_file


def pack_fixture(root):
    public=root/'blind-review-pack';public.mkdir(parents=True)
    private=root/'evaluator-only';private.mkdir()
    (private/'case-key.json').write_text('private-answer-sentinel',encoding='utf-8')
    (root/'human-labels.json').write_text('human-label-sentinel',encoding='utf-8')
    book=Workbook();book.active['A1']=42
    book.save(public/'artifact.xlsx');book.save(public/'input.xlsx');book.close()
    Image.new('RGB',(4,4),'white').save(public/'page.png')
    cases=[];pages=[]
    for index in range(12):
        identity=f'case-{index}'
        cases.append(dict(case_id=identity,cohort='standards-12',domain='excel',instruction='Preserve the input value42.',
            artifact='artifact.xlsx',artifact_hash=sha256_file(public/'artifact.xlsx'),inputs=['input.xlsx']))
        pages.append(dict(case_id=identity,status='available',pages=[dict(file='page.png',sha256=sha256_file(public/'page.png'),page=1)]))
    (public/'review-manifest.json').write_text(json.dumps({'rubric_hash':'a'*64,'cases':cases}),encoding='utf-8')
    (public/'rendered-pages.json').write_text(json.dumps(pages),encoding='utf-8')


def test_preparation_is_zero_call_and_excludes_labels_and_answer_key(tmp_path,monkeypatch):
    module=load_script('run_standard_judge_pilot.py')
    monkeypatch.setattr(module.ModelJudgementProvider,'judge',lambda *a,**k:pytest.fail('model during preparation'))
    pack=tmp_path/'pack';pack_fixture(pack)
    result=module.prepare(pack,tmp_path/'prepared')
    assert len(result['calls'])==24 and result['allowed_tool_calls']==0
    assert result['allow_live_calls'] is False
    assert result['schema_version']==module.REQUEST_VERSION
    assert result['prior_version_results_reused'] is False
    assert str((pack/'blind-review-pack/page.png').resolve()) in result['input_bindings']
    visual=json.loads((tmp_path/'prepared'/result['calls'][1]['request']).read_text(encoding='utf-8'))
    assert visual['requirement']['expected']['task_instruction']=='Preserve the input value42.'
    semantic=json.loads((tmp_path/'prepared'/result['calls'][0]['request']).read_text(encoding='utf-8'))
    assert 'delegated' in semantic['requirement']['expected']['review_scope']
    assert not json.loads((tmp_path/'prepared/proposed-live-policy.json').read_text(encoding='utf-8'))['allow_live_calls']
    text=''.join(p.read_text(encoding='utf-8') for p in (tmp_path/'prepared').glob('*.json'))
    assert 'private-answer-sentinel' not in text and 'human-label-sentinel' not in text
    payload=tmp_path/'prepared'/result['calls'][0]['request']
    payload.write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError,match='request changed'):
        module.execute(tmp_path/'prepared',tmp_path/'nonexistent-policy',tmp_path/'never')
    assert not (tmp_path/'never').exists()


def test_mandatory_partial_rejects_before_an_unrelated_missing_channel():
    module=load_script('run_standard_judge_pilot.py')
    assert module.aggregate_channels({'semantic':{'status':'NEEDS_REVIEW'},'visual':{'status':'PARTIAL'}})=='FAIL'
    assert module.aggregate_channels({'semantic':{'status':'PASS'}})=='INCOMPLETE'
    assert module.aggregate_channels({'semantic':{'status':'PASS'},'visual':{'status':'PASS'}})=='PASS'


def test_old_manifest_approval_cannot_start_new_cohort(tmp_path,monkeypatch):
    module=load_script('run_standard_judge_pilot.py')
    monkeypatch.setattr(module,'ModelJudgementProvider',lambda *a,**k:pytest.fail('provider constructed before authorization'))
    pack=tmp_path/'pack';pack_fixture(pack);module.prepare(pack,tmp_path/'prepared')
    policy=tmp_path/'policy.json';policy.write_text('{}',encoding='utf-8')
    (tmp_path/'approval-receipt.json').write_text(json.dumps({'policy_sha256':sha256_file(policy),'manifest_sha256':'0'*64}),encoding='utf-8')
    with pytest.raises(ValueError,match='approval does not bind'):
        module.execute(tmp_path/'prepared',policy,tmp_path/'never')
    assert not (tmp_path/'never').exists()


def test_continuation_skips_failed_attempt_and_retains_shared_budget():
    module=load_script('run_standard_judge_pilot.py')
    calls=[{'case_id':str(i),'modality':'semantic','request':str(i),'sha256':str(i)} for i in range(4)]
    manifest={'manifest_hash':'frozen','calls':calls}
    previous={'manifest_hash':'frozen','rows':[{**calls[0],'decision':{'status':'PASS'}},{**calls[1],'decision':None}]}
    rows,pending=module.continuation_rows(manifest,previous,{'calls':[{},{}]})
    assert rows[1]['decision'] is None and pending==calls[2:]
    with pytest.raises(ValueError,match='shared budget'):
        module.continuation_rows(manifest,previous,{'calls':[{}]})
    with pytest.raises(ValueError,match='different request cohort'):
        module.continuation_rows({**manifest,'manifest_hash':'changed'},previous,{'calls':[{},{}]})
