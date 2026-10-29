"""T06 independent champion, provenance, visibility and transport assertions."""
import io
import json
import subprocess

import pytest

from workagent_rsi import candidate_provider
from workagent_rsi.assessment_contracts import RSIFeedback
from workagent_rsi.candidate_provider import CodexCandidateProvider, OpenAIChatCandidateProvider
from workagent_rsi.hashing import canonical_json_hash
from workagent_rsi.workagent_provider import WorkAgentSkill


def champion(workspace, text='CHAMPION_read_all_input_rows'):
    workspace.mkdir(exist_ok=True)
    package = WorkAgentSkill(version='1.0.0', instructions=text).model_dump(mode='json')
    (workspace/'skill.json').write_text(json.dumps(package), encoding='utf-8')
    return package


def feedback():
    return RSIFeedback(tasks=[{'task_id':'dev-1','issues':[
        {'issue_id':'sum','requirement_id':'sum','kind':'artifact_defect','feedback_visibility':'develop',
         'observed':7,'expected':18,'location':{'artifact':'output','sheet':'Summary','cell':'B4'},
         'evidence_refs':['a'*64]}]}], issue_groups={'sum':['dev-1:sum']})


def offline_api(monkeypatch, requests):
    monkeypatch.setenv('T06_DUMMY_KEY', 'authored-no-account')
    def transport(request, timeout):
        requests.append(json.loads(request.data))
        # Invalid response is intentional; these cases test the outbound request.
        return io.BytesIO(b'{"choices":[{"message":{"content":"{}"}}]}')
    monkeypatch.setattr(candidate_provider.urllib.request, 'urlopen', transport)
    return OpenAIChatCandidateProvider(model='offline', api_base_url='https://offline.invalid/v1',
                                       api_key_env='T06_DUMMY_KEY', max_retries=0)


def builder():
    build = getattr(candidate_provider, 'build_candidate_context', None)
    assert callable(build), 'T06 requires one shared, independently verifiable context builder'
    return build


def test_api_compatibility_request_contains_actual_champion(tmp_path, monkeypatch):
    package=champion(tmp_path)
    requests=[]
    offline_api(monkeypatch,requests).generate_with_feedback(tmp_path,feedback(),'1.0.0',1,tmp_path/'records')
    serialized=json.dumps(requests)
    assert package['instructions'] in serialized
    assert canonical_json_hash(package) in serialized


def test_api_drops_protected_rows_issues_and_unknown_side_channels(tmp_path, monkeypatch):
    champion(tmp_path)
    data=feedback().model_dump()
    data['tasks'].extend([
        {'task_id':'PRIVATE_HIDDEN_TASK','hidden_test':True,'issues':[{'expected':'HIDDEN_ANSWER'}]},
        {'task_id':'PRIVATE_REG_TASK','split':'regression','trace':'REGRESSION_TRACE'},
    ])
    data['tasks'][0]['private_history']='/hidden/PRIVATE_PATH'
    data['tasks'][0]['issues'].append({'issue_id':'private','kind':'artifact_defect',
        'feedback_visibility':'evaluation_only','expected':'PRIVATE_ISSUE_CONCLUSION'})
    requests=[]
    offline_api(monkeypatch,requests).generate_with_feedback(tmp_path,RSIFeedback(**data),'1.0.0',1,tmp_path/'records')
    serialized=json.dumps(requests)
    assert 'PRIVATE_' not in serialized and 'HIDDEN_ANSWER' not in serialized and 'REGRESSION_TRACE' not in serialized
    assert 'dev-1' in serialized and 'Summary' in serialized


def test_missing_champion_rejected_before_cli_is_started(tmp_path):
    calls=[]
    provider=CodexCandidateProvider(tmp_path/'schema.json','offline',runner=lambda *a:calls.append(a))
    with pytest.raises((ValueError,FileNotFoundError),match='skill|champion'):
        provider.generate_with_feedback(tmp_path,feedback(),'1.0.0',1,tmp_path/'records')
    assert not calls


def test_registry_hash_and_parent_are_checked_against_exported_bytes(tmp_path):
    package=champion(tmp_path)
    build=builder()
    context=build(tmp_path,'1.0.0',1,feedback=feedback(),expected_champion_hash=canonical_json_hash(package))
    assert context.champion_package==package
    assert context.champion_hash==canonical_json_hash(package)
    with pytest.raises(ValueError,match='hash'):
        build(tmp_path,'1.0.0',1,feedback=feedback(),expected_champion_hash='b'*64)
    with pytest.raises(ValueError,match='parent|version'):
        build(tmp_path,'9.0.0',1,feedback=feedback())


def test_api_and_cli_share_context_and_save_identical_context_hash(tmp_path,monkeypatch):
    champion(tmp_path)
    context=builder()(tmp_path,'1.0.0',1,feedback=feedback())
    requests=[]
    api=offline_api(monkeypatch,requests)
    prompts=[]
    def runner(command,cwd,timeout):
        prompts.append(command[-1])
        return subprocess.CompletedProcess(command,0,stdout='',stderr='')
    cli=CodexCandidateProvider(tmp_path/'schema.json','offline',runner=runner)
    api.generate_with_context(context,tmp_path,tmp_path/'api-records')
    cli.generate_with_context(context,tmp_path,tmp_path/'cli-records')
    assert requests[0]['messages'][1]['content']==prompts[0]
    for name in ['api-records','cli-records']:
        saved=json.loads((tmp_path/name/'context.json').read_text())
        assert saved['context_hash']==context.fingerprint()
        assert saved['context']['champion_package']['instructions']=='CHAMPION_read_all_input_rows'


def test_context_budget_is_explicit_and_never_truncates_champion(tmp_path):
    champion(tmp_path,'KEEP_ALL_RULES_'*1000)
    with pytest.raises(ValueError,match='context.*budget|budget.*context'):
        builder()(tmp_path,'1.0.0',1,feedback=feedback(),max_context_bytes=512)
    assert 'KEEP_ALL_RULES_'*1000 in (tmp_path/'skill.json').read_text()


def test_previous_public_lesson_is_abstract_and_develop_provenance_is_checked(tmp_path):
    champion(tmp_path)
    old=feedback()
    context=builder()(tmp_path,'1.0.0',1,feedback=RSIFeedback(tasks=[]),public_feedback_history=[old])
    assert context.public_lessons
    lesson=context.public_lessons[0]
    assert lesson.source_split=='develop'
    assert lesson.source_feedback_hash==canonical_json_hash(old.model_dump(mode='json'))
    assert '18' not in lesson.statement and 'dev-1' not in lesson.statement and 'Summary' not in lesson.statement
    # Changing visibility must not launder a protected issue into an abstract lesson.
    private=RSIFeedback(tasks=[{'task_id':'PRIVATE_TASK','hidden_test':True,'issues':feedback().tasks[0]['issues']}])
    assert builder()(tmp_path,'1.0.0',1,feedback=RSIFeedback(tasks=[]),public_feedback_history=[private]).public_lessons==[]


def test_context_is_rechecked_before_transport_and_rejects_post_export_mutation(tmp_path,monkeypatch):
    champion(tmp_path)
    context=builder()(tmp_path,'1.0.0',1,feedback=feedback())
    champion(tmp_path,'changed after context export')
    requests=[]
    with pytest.raises(ValueError,match='champion|hash'):
        offline_api(monkeypatch,requests).generate_with_context(context,tmp_path,tmp_path/'records')
    assert not requests


def test_second_round_receives_promoted_champion_and_previous_public_lessons(tmp_path):
    from test_rsi_artifact_feedback import setup_loop
    from workagent_rsi.artifact_candidate import ArtifactFeedbackProvider
    class CaptureProvider(ArtifactFeedbackProvider):
        def __init__(self):self.contexts=[]
        def generate_with_context(self,context,workspace,record_root):
            self.contexts.append(context)
            return self.generate_with_feedback(workspace,context.develop_feedback,context.parent_version,context.edit_budget,record_root)
    provider=CaptureProvider()
    loop,args=setup_loop(tmp_path,provider=provider)
    result=loop.run(**args,rounds=2)
    assert result['status']=='completed',result.get('failure')
    assert len(provider.contexts)==2
    assert provider.contexts[0].champion_package['sales_rows']=='omit_last'
    assert provider.contexts[1].champion_package['sales_rows']=='all'
    assert provider.contexts[1].champion_hash==result['rounds'][0]['champion_after']['content_hash']
    assert provider.contexts[1].parent_version==result['rounds'][0]['champion_after']['version']
    assert provider.contexts[1].public_lessons
    assert 'PRIVATE_REGION' not in provider.contexts[1].model_dump_json()
    assert provider.contexts[0].develop_feedback.tasks[0]['requirement_refs']
    assert provider.contexts[0].develop_feedback.tasks[0]['trace_summary']['visible_issue_count'] > 0


def test_nested_context_mutation_is_rejected_before_transport(tmp_path,monkeypatch):
    champion(tmp_path)
    context=builder()(tmp_path,'1.0.0',1,feedback=feedback())
    context.develop_feedback.tasks.append({'task_id':'PRIVATE_TASK','split':'hidden'})
    requests=[]
    with pytest.raises(ValueError,match='unapproved'):
        offline_api(monkeypatch,requests).generate_with_context(context,tmp_path,tmp_path/'records')
    assert not requests


def test_api_compatibility_adapter_enforces_context_budget_before_transport(tmp_path,monkeypatch):
    champion(tmp_path,'large rule '*1000)
    requests=[]
    provider=offline_api(monkeypatch,requests)
    provider.max_context_bytes=512
    with pytest.raises(ValueError,match='context budget'):
        provider.generate_with_feedback(tmp_path,feedback(),'1.0.0',1,tmp_path/'records')
    assert not requests


def test_loop_rejects_stale_export_instead_of_supplying_wrong_champion(tmp_path):
    from test_rsi_artifact_feedback import setup_loop
    loop,args=setup_loop(tmp_path)
    (args['source_root']/'skill.json').write_text('{"sales_rows":"all"}')
    with pytest.raises(ValueError,match='champion hash'):
        loop.run_round(**args)
    assert not (args['run_root']/'provider_records').exists()


def test_private_promotion_evidence_is_not_exported_as_public_history(tmp_path):
    from test_rsi_artifact_feedback import setup_loop
    loop,args=setup_loop(tmp_path)
    result=loop.run_round(**args,inherited_evidence_refs=['PRIVATE_PROTECTED_PROMOTION_REASON'])
    assert result['status']=='completed'
    workspace=args['run_root']/'candidate_workspace'
    assert not (workspace/'inherited_evidence.json').exists()
    assert all('PRIVATE_PROTECTED_PROMOTION_REASON' not in p.read_text(encoding='utf-8')
               for p in workspace.glob('*.json'))


def test_resume_checks_previous_develop_feedback_provenance(tmp_path):
    from test_rsi_artifact_feedback import setup_loop
    loop,args=setup_loop(tmp_path)
    first=loop.run(**args,rounds=1)
    assert first['status']=='completed'
    path=args['run_root']/'round-01/develop_feedback.json'
    value=json.loads(path.read_text())
    value['tasks'][0]['quality_score']=999
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='history hash'):
        loop.run(**args,rounds=2,resume_root=args['run_root'])
