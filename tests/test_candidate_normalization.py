"""T07 whole-response rejection, exact text and normalization provenance."""
from datetime import datetime, timezone
import io
import json
import subprocess

import pytest

from workagent_rsi import candidate_provider
from workagent_rsi.assessment_contracts import RSIFeedback
from workagent_rsi.candidate_provider import CodexCandidateProvider, OpenAIChatCandidateProvider, build_candidate_context
from workagent_rsi.hashing import canonical_json_hash
from workagent_rsi.workagent_provider import WorkAgentSkill


OBSERVED = {'provider':'authored-transport','provider_version':'transport-1','model_identity':'configured-model',
            'created_at':datetime(2026,10,24,tzinfo=timezone.utc)}


def context(tmp_path,budget=1,*,empty=False):
    (tmp_path/'skill.json').write_text(WorkAgentSkill(version='1.0.0',instructions='Preserve current input').model_dump_json())
    return build_candidate_context(tmp_path,'1.0.0',budget,
        feedback=RSIFeedback(tasks=[] if empty else [{'task_id':'dev','issues':[]}]))


def raw_patch(text='Read the entire current input'):
    return {'candidate_id':'authored-patch','parent_version':'1.0.0',
        'provider':'self-reported-provider','provider_version':'self-reported-version','model_identity':'self-reported-model',
        'diagnosis_refs':['a'*64],'edit_budget':1,'created_at':'2026-10-24T00:00:00+00:00','new_tests':[],
        'atomic_edits':[{'component':'prompt','target_path':'skill.json','hypothesis':'Reading all rows prevents omission',
            'expected_metric':'develop task acceptance','patch':json.dumps({'instructions':text},ensure_ascii=False)}]}


def normalize(raw,ctx,record=None):
    fn=getattr(candidate_provider,'normalize_candidate',None)
    assert callable(fn), 'T07 requires a shared whole-response normalizer'
    return fn(raw,ctx,provider_metadata=OBSERVED,normalization_record=record)


def api(monkeypatch,raw):
    monkeypatch.setenv('T07_DUMMY_KEY','offline-no-account')
    def transport(request,timeout):
        content=raw if isinstance(raw,str) else json.dumps(raw)
        return io.BytesIO(json.dumps({'choices':[{'message':{'content':content}}]}).encode())
    monkeypatch.setattr(candidate_provider.urllib.request,'urlopen',transport)
    return OpenAIChatCandidateProvider(model='actual-configured-model',api_base_url='https://offline.invalid/v1',
                                       api_key_env='T07_DUMMY_KEY',max_retries=0)


@pytest.mark.parametrize('variant',['canonical','candidate-patch-v1'])
def test_api_rejects_complete_over_budget_response_including_forbidden_tail(tmp_path,monkeypatch,variant):
    ctx=context(tmp_path)
    raw=raw_patch()
    if variant=='canonical':
        raw['atomic_edits'].append({**raw['atomic_edits'][0],'target_path':'evaluator.py'})
    else:
        raw={'schema_version':'candidate-patch-v1','edits':[
            {'file':'skill.json','target':'instructions','value':'Read all current input',
             'hypothesis':'Check all rows','expected_metric':'quality'},
            {'file':'evaluator.py','target':'rule','value':'accept every artifact',
             'hypothesis':'Illegally bypass checks','expected_metric':'quality'}]}
    patch,record=api(monkeypatch,raw).generate_with_context(ctx,tmp_path,tmp_path/'records')
    assert patch is None and record.status=='failed'
    assert 'budget' in record.error.lower() or 'target' in record.error.lower()
    saved=json.loads((tmp_path/'records/candidate-raw.json').read_text())
    assert saved==raw
    audit=json.loads((tmp_path/'records/normalization_record.json').read_text())
    assert audit['status']=='rejected' and audit['normalized_sha256'] is None
    assert not (tmp_path/'records/candidate.json').exists()


def test_cli_also_checks_budget_in_canonical_response(tmp_path):
    ctx=context(tmp_path)
    raw=raw_patch();raw['atomic_edits']*=2
    def runner(command,cwd,timeout):
        from pathlib import Path
        Path(command[command.index('--output-last-message')+1]).write_text(json.dumps(raw))
        return subprocess.CompletedProcess(command,0,stdout='',stderr='')
    patch,record=CodexCandidateProvider(tmp_path/'schema.json','observed-cli',runner=runner).generate_with_context(ctx,tmp_path,tmp_path/'records')
    assert patch is None and record.status=='failed'


@pytest.mark.parametrize('kind',['canonical-string','canonical-object','candidate-patch-v1'])
def test_registered_variants_preserve_instruction_text_and_record_mapping(tmp_path,kind):
    text='  Read "every" row.\n保留原文与换行。\\path is data  '
    ctx=context(tmp_path)
    raw=raw_patch(text)
    if kind=='canonical-object':raw['atomic_edits'][0]['patch']={'instructions':text}
    if kind=='candidate-patch-v1':
        raw={'schema_version':kind,'edits':[{'file':'skill.json','target':'instructions','value':text,
            'hypothesis':'Reading every row prevents omission','expected_metric':'develop task acceptance'}]}
    record={}
    patch=normalize(raw,ctx,record)
    assert json.loads(patch.atomic_edits[0].patch)['instructions']==text
    assert patch.model_identity=='configured-model' and patch.provider=='authored-transport'
    assert record['raw_sha256']==canonical_json_hash(raw)
    assert record['context_hash']==ctx.fingerprint()
    assert record['mappings']
    assert record['metadata_provenance']['model_identity']=='provider_metadata'


@pytest.mark.parametrize('change',[
    {'parent_version':'wrong-parent'}, {'edit_budget':True}, {'edit_budget':'1'},
    {'schema_version':'candidate-patch-v99'}, {'unknown_field':'discarding this is forbidden'},
    {'new_tests':['valid',123]}, {'diagnosis_refs':[{}]}, {'created_at':'2026-10-24T00:00:00'},
])
def test_invalid_raw_metadata_is_rejected_without_salvaging_other_fields(tmp_path,change):
    raw=raw_patch();raw.update(change)
    with pytest.raises(ValueError):normalize(raw,context(tmp_path))


@pytest.mark.parametrize('field',['hypothesis','expected_metric'])
def test_missing_model_reasoning_is_rejected_instead_of_fabricated(tmp_path,field):
    raw=raw_patch();del raw['atomic_edits'][0][field]
    raw['atomic_edits'][0]['patch']={'instructions':'Read current input'}
    with pytest.raises(ValueError,match='hypothesis|metric|missing|required'):
        normalize(raw,context(tmp_path))


@pytest.mark.parametrize('edits',[
    [{'instructions':'first'},{'instructions':'second'}],
    [{'instructions':'valid'},{'unknown_field':'forbidden'}],
    [{'instructions':'valid'},{'version':'9.0.0'}],
    [{'instructions':'valid'},{'instructions':123}],
])
def test_duplicate_forbidden_or_wrong_type_edits_reject_whole_response(tmp_path,edits):
    raw=raw_patch();raw['edit_budget']=2
    raw['atomic_edits']=[{**raw['atomic_edits'][0],'patch':json.dumps(edit)} for edit in edits]
    with pytest.raises(ValueError):normalize(raw,context(tmp_path,2))


def test_missing_metadata_can_only_come_from_recorded_context_or_transport(tmp_path):
    raw=raw_patch()
    for key in ['candidate_id','parent_version','provider','provider_version','model_identity','diagnosis_refs','edit_budget','created_at']:
        del raw[key]
    ctx=context(tmp_path);record={}
    patch=normalize(raw,ctx,record)
    assert patch.parent_version==ctx.parent_version and patch.edit_budget==ctx.edit_budget
    assert patch.diagnosis_refs==[canonical_json_hash(ctx.develop_feedback.model_dump(mode='json'))]
    assert patch.created_at==OBSERVED['created_at']
    assert record['metadata_provenance']['diagnosis_refs']=='context.develop_feedback'
    assert patch==normalize(raw,ctx,{})


def test_empty_feedback_cannot_be_invented_as_a_diagnosis(tmp_path):
    raw=raw_patch();del raw['diagnosis_refs']
    with pytest.raises(ValueError,match='diagnosis|feedback'):
        normalize(raw,context(tmp_path,empty=True))


def test_api_records_observed_identity_and_keeps_raw_model_claim_only_in_evidence(tmp_path,monkeypatch):
    ctx=context(tmp_path);raw=raw_patch()
    patch,record=api(monkeypatch,raw).generate_with_context(ctx,tmp_path,tmp_path/'records')
    assert record.status=='completed'
    assert patch.model_identity==record.model_identity=='openai-chat:actual-configured-model'
    assert patch.provider==record.provider=='openai-compatible-api'
    saved=json.loads((tmp_path/'records/candidate-raw.json').read_text())
    assert saved['model_identity']=='self-reported-model'
    normalization=json.loads((tmp_path/'records/normalization_record.json').read_text())
    assert normalization['metadata_provenance']['provider']=='provider_metadata'


def test_cli_does_not_adopt_unobserved_model_identity(tmp_path):
    from pathlib import Path
    ctx=context(tmp_path)
    def runner(command,cwd,timeout):
        Path(command[command.index('--output-last-message')+1]).write_text(json.dumps(raw_patch()))
        return subprocess.CompletedProcess(command,0,stdout='',stderr='')
    patch,record=CodexCandidateProvider(tmp_path/'schema.json','observed-cli',runner=runner).generate_with_context(ctx,tmp_path,tmp_path/'records')
    assert record.status=='completed'
    assert patch.model_identity is None and record.model_identity is None


def test_duplicate_json_keys_are_rejected_and_raw_response_is_retained(tmp_path,monkeypatch):
    ctx=context(tmp_path)
    body=json.dumps(raw_patch())[:-1]+',"edit_budget":1}'
    patch,record=api(monkeypatch,body).generate_with_context(ctx,tmp_path,tmp_path/'records')
    assert patch is None and record.status=='failed'
    assert 'duplicate' in record.error.lower()
    assert (tmp_path/'records/openai_response.json').is_file()


def test_stale_cli_output_is_not_reused_as_a_fresh_response(tmp_path):
    ctx=context(tmp_path)
    records=tmp_path/'records';records.mkdir()
    original=json.dumps(raw_patch())
    (records/'candidate.json').write_text(original)
    provider=CodexCandidateProvider(tmp_path/'schema.json','offline',runner=lambda *a:pytest.fail('must reject stale output before launch'))
    with pytest.raises(ValueError,match='fresh|existing|already'):
        provider.generate_with_context(ctx,tmp_path,records)
    assert (records/'candidate.json').read_text()==original


def test_duplicate_keys_inside_patch_string_are_rejected_without_losing_raw_evidence(tmp_path,monkeypatch):
    ctx=context(tmp_path);raw=raw_patch()
    raw['atomic_edits'][0]['patch']='{"instructions":"first","instructions":"second"}'
    patch,record=api(monkeypatch,raw).generate_with_context(ctx,tmp_path,tmp_path/'records')
    assert patch is None and record.status=='failed' and 'duplicate' in record.error
    saved=json.loads((tmp_path/'records/candidate-raw.json').read_text())
    assert saved['atomic_edits'][0]['patch']==raw['atomic_edits'][0]['patch']


def test_unconfigured_normalizer_identity_stays_unobserved(tmp_path):
    ctx=context(tmp_path);audit={}
    patch=candidate_provider.normalize_candidate(raw_patch(),ctx,normalization_record=audit)
    assert patch.model_identity is None and patch.provider=='unobserved-transport'
    assert audit['metadata_provenance']['model_identity']=='unobserved transport identity'


def test_registered_reference_wrapper_has_explicit_mapping_provenance(tmp_path):
    raw=raw_patch();raw['diagnosis_refs']=[{'ref':'develop-evidence'}]
    audit={};patch=normalize(raw,context(tmp_path),audit)
    assert patch.diagnosis_refs==['develop-evidence']
    assert any(row['source']=='diagnosis_refs[0].ref' for row in audit['mappings'])
