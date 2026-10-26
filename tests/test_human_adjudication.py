import json
from pathlib import Path

import pytest

from workagent_rsi.hashing import canonical_json_hash, sha256_file
from workagent_rsi.human_adjudication import intake_adjudication
from workagent_rsi.human_calibration import intake_human_submission


def fixture(tmp_path):
    rubric='a'*64
    manifest={'rubric_hash':rubric,'case_ids':['one','two']}
    original=tmp_path/'original.json'
    original.write_text(json.dumps({'rubric_hash':rubric,'labels':[
        {'case_id':'one','label':'PASS'},{'case_id':'two','label':'FAIL'}]}),encoding='utf-8')
    intake_human_submission(original,tmp_path/'blind',reviewer_id='test-reviewer',
        evidence_ref='authored provenance fixture',review_manifest=manifest)
    public=tmp_path/'public';public.mkdir();(public/'page.png').write_bytes(b'authored bound asset')
    request={'case_ids':['one','two'],'rubric_hash':rubric,
        'source_submission_hash':sha256_file(original),'asset_bindings':{'page.png':sha256_file(public/'page.png')}}
    request['request_manifest_hash']=canonical_json_hash(request)
    request_file=tmp_path/'request.json';request_file.write_text(json.dumps(request),encoding='utf-8')
    payload={'schema_version':'office-human-adjudication-v1','source_kind':'human_adjudication',
        'rubric_hash':rubric,'source_submission_hash':sha256_file(original),
        'request_manifest_hash':request['request_manifest_hash'],'adjudication_after_diagnostics':True,
        'independent_blind_review':False,'labels':[{'case_id':cid,'reviewer_id':'test-reviewer',
            'label':label,'defect_locations':['Checked source and identified this reason.'],
            'requirements_checked':True,'timestamp':'2026-10-26T14:00:00Z'}
            for cid,label in [('one','FAIL'),('two','INCOMPLETE')]]}
    submitted=tmp_path/'adjudication.json';submitted.write_text(json.dumps(payload),encoding='utf-8')
    return submitted,payload,dict(request_file=request_file,original_intake=tmp_path/'blind',
        public_root=public,evidence_ref='authored external adjudication fixture')


def test_adjudication_preserves_original_and_never_adds_independent_blind_labels(tmp_path):
    submitted,payload,kwargs=fixture(tmp_path)
    original=kwargs['original_intake']/'human-labels.jsonl';before=original.read_bytes()
    receipt=intake_adjudication(submitted,tmp_path/'revision',**kwargs)
    assert receipt['accepted_adjudications']==receipt['changed_from_original']==2
    assert receipt['new_independent_blind_labels']==0 and not receipt['reference_gate_passed']
    assert original.read_bytes()==before
    assert (tmp_path/'revision/external-submission.json').read_bytes()==submitted.read_bytes()
    with pytest.raises(ValueError,match='unknown submission source'):
        intake_human_submission(submitted,tmp_path/'forged-blind',reviewer_id='test-reviewer',
            evidence_ref='fixture',review_manifest={'rubric_hash':payload['rubric_hash'],'case_ids':['one','two']})


def test_changed_assets_or_parent_binding_reject_before_creating_output(tmp_path):
    submitted,payload,kwargs=fixture(tmp_path)
    payload['source_submission_hash']='b'*64;submitted.write_text(json.dumps(payload),encoding='utf-8')
    with pytest.raises(ValueError,match='original submission binding changed'):
        intake_adjudication(submitted,tmp_path/'rejected',**kwargs)
    payload['source_submission_hash']=sha256_file(kwargs['original_intake']/'external-submission.json')
    submitted.write_text(json.dumps(payload),encoding='utf-8')
    (kwargs['public_root']/'page.png').write_bytes(b'changed')
    with pytest.raises(ValueError,match='artifact/page changed'):
        intake_adjudication(submitted,tmp_path/'rejected',**kwargs)
    labels=kwargs['original_intake']/'human-labels.jsonl'
    rows=[json.loads(line) for line in labels.read_text(encoding='utf-8').splitlines()]
    rows[0]['label']='FAIL'
    labels.write_text('\n'.join(json.dumps(row) for row in rows),encoding='utf-8')
    with pytest.raises(ValueError,match='normalized original labels differ'):
        intake_adjudication(submitted,tmp_path/'rejected',**kwargs)
    assert not (tmp_path/'rejected').exists()


def test_duplicate_cases_unchecked_requirements_and_model_reviewers_are_rejected(tmp_path):
    submitted,payload,kwargs=fixture(tmp_path)
    first=payload['labels'][0]
    payload['labels'][1]['case_id']='one';submitted.write_text(json.dumps(payload),encoding='utf-8')
    with pytest.raises(ValueError,match='each requested case exactly once'):
        intake_adjudication(submitted,tmp_path/'rejected',**kwargs)
    payload['labels'][1]['case_id']='two';first['requirements_checked']=1
    submitted.write_text(json.dumps(payload),encoding='utf-8')
    with pytest.raises(ValueError,match='explicit requirements-check'):
        intake_adjudication(submitted,tmp_path/'rejected',**kwargs)
    first['requirements_checked']=True;first['reviewer_id']='gpt-model'
    submitted.write_text(json.dumps(payload),encoding='utf-8')
    with pytest.raises(ValueError,match='model identity'):
        intake_adjudication(submitted,tmp_path/'rejected',**kwargs)
    assert not (tmp_path/'rejected').exists()
