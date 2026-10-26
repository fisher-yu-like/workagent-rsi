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
    text=''.join(p.read_text(encoding='utf-8') for p in (tmp_path/'prepared').glob('*.json'))
    assert 'private-answer-sentinel' not in text and 'human-label-sentinel' not in text
    payload=tmp_path/'prepared'/result['calls'][0]['request']
    payload.write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError,match='request changed'):
        module.execute(tmp_path/'prepared',tmp_path/'nonexistent-policy',tmp_path/'never')
    assert not (tmp_path/'never').exists()
