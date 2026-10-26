"""Human provenance is not inferred from an agent-supplied reviewer name."""
import pytest


def api():
    import importlib.util
    assert importlib.util.find_spec('workagent_rsi.human_calibration'), 'T28 human-calibration implementation missing'
    from workagent_rsi.human_calibration import HumanLabel, compare_human_labels
    return HumanLabel, compare_human_labels


def test_missing_labels_block_without_fake_agreement():
    _, compare = api()
    result = compare([], [], review_manifest={'case_ids':['opaque-1'], 'rubric_hash':'a'*64})
    assert result['status'] == 'blocked' and result['agreement']['value'] is None
    assert result['agreement']['denominator'] == 0


def test_model_labels_and_self_signed_receipts_are_rejected():
    Label, compare = api()
    base = dict(case_id='opaque-1',reviewer_id='person',label='PASS',defect_locations=[],
        timestamp='2026-10-25T10:00:00+08:00',evidence_ref='submission-1',rubric_hash='a'*64,
        source_kind='human',submission_hash='b'*64)
    with pytest.raises(ValueError):
        Label(**{**base,'reviewer_id':'Codex','source_kind':'model'})
    with pytest.raises(ValueError):
        Label(**{**base,'model_identity':'gpt-6.1-sol'})
    label = Label(**base)
    result = compare([label], [], review_manifest={'case_ids':['opaque-1'],'rubric_hash':'a'*64})
    assert result['status']=='blocked' and result['accepted_human_labels']==0


def test_rubric_and_blinding_receipts_bind_actual_user_submission():
    Label, compare = api()
    label = Label(case_id='opaque-1',reviewer_id='user',label='FAIL',defect_locations=['slide2'],
        timestamp='2026-10-25T10:00:00+08:00',evidence_ref='submission-1',rubric_hash='a'*64,
        source_kind='human',submission_hash='b'*64)
    manifest = {'case_ids':['opaque-1'], 'rubric_hash':'a'*64}
    receipt = {'source_kind':'user_message', 'submission_hash':'b'*64,'reviewer_id':'user',
        'evidence_ref':'submission-1','case_ids':['opaque-1'],'rubric_hash':'a'*64,
        'received_at':'2026-10-25T02:00:00+00:00','judge_revealed':False}
    decision = {'case_id':'opaque-1','status':'PASS','rubric_hash':'a'*64,'evaluator_identity':'evaluator-v1'}
    report = compare([label],[decision],review_manifest=manifest,submission_receipts=[receipt])
    assert report['status']=='completed' and report['critical_false_accepts']==1
    assert report['quality_qualified'] is False
    with pytest.raises(ValueError, match='rubric'):
        compare([label],[{**decision,'rubric_hash':'c'*64}],review_manifest=manifest,submission_receipts=[receipt])
    with pytest.raises(ValueError, match='blind|revealed'):
        compare([label],[decision],review_manifest=manifest,submission_receipts=[{**receipt,'judge_revealed':True}])
    from workagent_rsi.human_calibration import evaluator_identity_for_rubric
    assert evaluator_identity_for_rubric('base',{'version':1})!=evaluator_identity_for_rubric('base',{'version':2})


def test_external_file_intake_preserves_exact_source_and_rejects_model_claim(tmp_path):
    api()
    import json,hashlib
    from workagent_rsi.human_calibration import intake_human_submission,compare_human_labels
    manifest={'case_ids':['opaque-1'],'rubric_hash':'a'*64}
    payload={'rubric_hash':'a'*64,'labels':[{'case_id':'opaque-1','label':'PASS','defect_locations':[]}]}
    source=tmp_path/'external.json';source.write_text(json.dumps(payload))
    receipt=intake_human_submission(source,tmp_path/'intake',reviewer_id='user',evidence_ref='authored-test-external-submission',review_manifest=manifest)
    assert receipt['submission_hash']==hashlib.sha256(source.read_bytes()).hexdigest()
    assert (tmp_path/'intake/external-submission.json').read_bytes()==source.read_bytes()
    assert compare_human_labels([],[],review_manifest={'case_ids':[],'rubric_hash':'a'*64})['status']=='blocked'
    source.write_text(json.dumps({**payload,'source_kind':'model'}))
    with pytest.raises(ValueError,match='model'):
        intake_human_submission(source,tmp_path/'never',reviewer_id='user',evidence_ref='test',review_manifest=manifest)


def test_quick_uncertain_human_labels_are_preserved_but_cannot_qualify_judge(tmp_path):
    import json
    from workagent_rsi.human_calibration import intake_human_submission,compare_human_labels
    manifest={'case_ids':['opaque-1'],'rubric_hash':'a'*64}
    payload={'rubric_hash':'a'*64,'labels':[{'case_id':'opaque-1','label':'FAIL','defect_locations':['page2']}]}
    source=tmp_path/'external.json';source.write_text(json.dumps(payload),encoding='utf-8')
    receipt=intake_human_submission(source,tmp_path/'intake',reviewer_id='user',evidence_ref='actual-user-file',
        review_manifest=manifest,review_depth='quick_visual',reviewer_uncertain=True,review_note='Reviewer disclosed a quick scan.')
    labels=[json.loads(line) for line in (tmp_path/'intake/human-labels.jsonl').read_text(encoding='utf-8').splitlines()]
    assert receipt['reference_status']=='provisional'
    assert (tmp_path/'intake/external-submission.json').read_bytes()==source.read_bytes()
    decisions=[dict(case_id='opaque-1',status='PASS',rubric_hash='a'*64,evaluator_identity='same-evaluator')]
    report=compare_human_labels(labels,decisions,review_manifest=manifest,submission_receipts=[receipt])
    assert report['accepted_human_labels']==1 and report['human_fail_judge_pass']==1
    assert report['critical_false_accepts'] is None
    assert not report['reference_gate_passed'] and not report['critical_gate_passed']
    assert not report['quality_qualified']


def test_unspecified_intake_does_not_assert_detailed_review(tmp_path):
    import json
    from workagent_rsi.human_calibration import intake_human_submission
    source=tmp_path/'external.json';source.write_text(json.dumps({'rubric_hash':'a'*64,'labels':[]}),encoding='utf-8')
    receipt=intake_human_submission(source,tmp_path/'intake',reviewer_id='user',evidence_ref='test',
        review_manifest={'case_ids':[],'rubric_hash':'a'*64})
    assert receipt['review_depth']=='unspecified' and receipt['reference_status']=='provisional'
    assert not (tmp_path/'never').exists()
