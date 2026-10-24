"""T05 independent allowlist, source identity and controlled-worker boundaries."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest
from openpyxl import Workbook
from pydantic import ValidationError

from workagent_rsi.candidate_workspace import CandidateWorkspaceBuilder
from workagent_rsi.contracts import TaskSpec
from workagent_rsi.workagent_office import copy_task_inputs
from workagent_rsi.artifact_renderer import OfficeArtifactRenderer
from workagent_rsi.execution_sandbox import SandboxPolicy
from workagent_rsi.run_contracts import ExecutionOutcome


def link_directory(link, target):
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
        assert result.returncode == 0


def workbook(path):
    book = Workbook()
    book.active['A1'] = 'authored-input'
    book.save(path)
    return path


def task(*inputs):
    return TaskSpec(task_id='isolation', domain='excel', instruction='Use only the supplied workbook', input_files=tuple(inputs))


def test_candidate_rejects_internal_source_junction_before_resolving(tmp_path):
    source = tmp_path / 'source'
    (source / 'ordinary').mkdir(parents=True)
    (source / 'ordinary/skill.json').write_text('{"instructions":"read current inputs"}')
    link_directory(source / 'alias', source / 'ordinary')
    with pytest.raises(ValueError, match='symlink|reparse'):
        CandidateWorkspaceBuilder().export(source, tmp_path / 'candidate', ['alias/skill.json'], {})


def test_candidate_rejects_linked_source_root(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'skill.json').write_text('{}')
    link_directory(tmp_path / 'alias', source)
    with pytest.raises(ValueError, match='symlink|reparse'):
        CandidateWorkspaceBuilder().export(tmp_path / 'alias', tmp_path / 'candidate', ['skill.json'], {})


def test_candidate_rejects_history_even_when_its_basename_is_innocuous(tmp_path):
    source = tmp_path / 'source'
    (source / 'project_artifacts/results/history').mkdir(parents=True)
    (source / 'project_artifacts/results/history/report.json').write_text('{"hidden_answer":"sentinel"}')
    with pytest.raises(ValueError, match='protected'):
        CandidateWorkspaceBuilder().export(source, tmp_path / 'candidate',
                                           ['project_artifacts/results/history/report.json'], {})


def test_candidate_context_cannot_replace_champion_or_workspace_policy(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'skill.json').write_text('{"instructions":"champion sentinel"}')
    with pytest.raises(ValueError, match='collision|reserved'):
        CandidateWorkspaceBuilder().export(source, tmp_path / 'candidate', ['skill.json'], {'skill.json':'{}'})


def test_execution_view_rejects_existing_files_and_workspace_junction(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    workbook(source / 'input.xlsx')
    destination = tmp_path / 'existing'
    destination.mkdir()
    (destination / 'hidden-result.json').write_text('excluded sentinel')
    with pytest.raises(ValueError, match='empty'):
        copy_task_inputs(task('input.xlsx'), destination, source)
    empty = tmp_path / 'empty'
    empty.mkdir()
    link_directory(tmp_path / 'linked-view', empty)
    with pytest.raises(ValueError, match='symlink|reparse'):
        copy_task_inputs(task('input.xlsx'), tmp_path / 'linked-view', source)


def test_execution_view_exports_only_declared_inputs_not_accepted_answers(tmp_path):
    from workagent_rsi.workagent_office import prepare_execution_view
    source = tmp_path / 'source'
    source.mkdir()
    workbook(source / 'input.xlsx')
    workbook(source / 'answer.xlsx')
    (source / 'hidden.jsonl').write_text('hidden sentinel')
    target = tmp_path / 'view'
    manifest = prepare_execution_view(task('input.xlsx'), source, target)
    assert {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()} == {
        'input_manifest.json','inputs/0001-input.xlsx'}
    assert 'answer.xlsx' not in json.dumps(manifest) and 'hidden sentinel' not in json.dumps(manifest)
    assert (source / 'input.xlsx').read_bytes() == (target / 'inputs/0001-input.xlsx').read_bytes()


def test_renderer_rejects_wrong_trusted_hash_before_invoking_any_worker(tmp_path, monkeypatch):
    source = workbook(tmp_path / 'input.xlsx')
    monkeypatch.setattr('workagent_rsi.artifact_renderer.subprocess.run', lambda *a,**k: pytest.fail('no worker before hash validation'))
    result = OfficeArtifactRenderer(tmp_path / 'renders').render(source, 'excel', 'a'*64)
    assert result.status == 'error' and 'hash' in result.error.lower()


def test_unconfigured_renderer_is_unavailable_without_touching_user_office(tmp_path, monkeypatch):
    source = workbook(tmp_path / 'input.xlsx')
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    monkeypatch.setattr('workagent_rsi.artifact_renderer.subprocess.run', lambda *a,**k: pytest.fail('unconfigured worker must not start Office'))
    result = OfficeArtifactRenderer(tmp_path / 'renders').render(source, 'excel', before)
    assert result.status == 'unavailable'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_render_policy_cannot_enable_macros_or_external_updates():
    from workagent_rsi.artifact_renderer import RenderPolicy
    for change in ({'macros':'enabled'}, {'update_external_links':True}, {'read_only_copy':False}, {'cleanup':'all_new_processes'}):
        with pytest.raises(ValidationError):
            RenderPolicy(**change)


class AuthoredRenderStub:
    policy = SandboxPolicy()
    def __init__(self, *, change_copy=False, bad_policy=False, bad_page=False):
        self.change_copy, self.bad_policy, self.bad_page = change_copy, bad_policy, bad_page
        self.views = []

    def run(self, script, view, timeout):
        from PIL import Image
        self.views.append(view)
        config = json.loads((view/'inputs/render-policy.json').read_text())
        assert {p.name for p in (view/'inputs').iterdir()} == {'artifact.xlsx','render-policy.json'}
        assert config['policy']['macros']=='never' and config['policy']['update_external_links'] is False
        output = view/'outputs'
        output.mkdir()
        page = output/'page-1.png'
        Image.new('RGB',(80,60),'white').save(page)
        load = {'ReadOnly':True,'MacroExecutionMode':0,'UpdateDocMode':0}
        if self.bad_policy: load['UpdateDocMode']=3
        report = {'status':'available','source_sha256':config['source_sha256'],'owned_cleanup':True,
                  'load_policy':load,'environment':{'office_version':'authored-unit-stub','font_fingerprint':'stub'},
                  'pages':[{'page':1,'file':'outputs/../secret.png' if self.bad_page else 'outputs/page-1.png',
                            'sha256':hashlib.sha256(page.read_bytes()).hexdigest()}]}
        if self.change_copy:(view/config['source']).write_bytes(b'authored unauthorized mutation')
        (output/'render-metadata.json').write_text(json.dumps(report))
        return ExecutionOutcome(status='succeeded')


def test_renderer_only_passes_copy_and_policy_to_worker_and_never_reuses_pages(tmp_path):
    source = workbook(tmp_path/'input.xlsx')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    worker = AuthoredRenderStub()
    renderer = OfficeArtifactRenderer(tmp_path/'renders',sandbox=worker)
    first = renderer.render(source,'excel',digest)
    second = renderer.render(source,'excel',digest)
    assert first.status == second.status == 'available'
    assert first.pages[0].width==80 and first.pages[0].height==60
    assert first.pages[0].path != second.pages[0].path
    assert worker.views[0] != worker.views[1]
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest


@pytest.mark.parametrize('changes',[{'change_copy':True},{'bad_policy':True},{'bad_page':True}])
def test_invalid_worker_proof_never_produces_available_pages(tmp_path,changes):
    source = workbook(tmp_path/'input.xlsx')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    result = OfficeArtifactRenderer(tmp_path/'renders',sandbox=AuthoredRenderStub(**changes)).render(source,'excel',digest)
    assert result.status=='error' and result.pages==[]
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest


def test_stored_com_verification_hashes_copy_and_preserves_source(tmp_path):
    from workagent_rsi.artifact_com import verify_stored_office_artifacts
    source = workbook(tmp_path/'input.xlsx')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    calls = []
    def controlled_test_callback(path,domain):
        assert path != source and domain=='excel'
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
        calls.append(path)
        return {'ok':True,'status':'available','version':'authored-stub'}
    reference = {'path':str(source),'sha256':digest,
                 'media_type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
    result = verify_stored_office_artifacts([reference],'excel',tmp_path,verify=controlled_test_callback)
    assert result['ok'] is True and len(calls)==1
    assert result['formula_recalculation']==result['visual_validation']=='not_claimed'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    reference['sha256']='a'*64
    result = verify_stored_office_artifacts([reference],'excel',tmp_path,verify=controlled_test_callback)
    assert result['ok'] is False and len(calls)==1


def test_explicit_com_worker_requires_load_and_ownership_proof(tmp_path):
    from workagent_rsi.office_capabilities import verify_artifact_with_com
    source = workbook(tmp_path/'input.xlsx')
    class UnsafeWorker:
        def reopen(self,path,domain,**kwargs):
            assert path!=source
            return {'ok':True,'status':'available'}
    result=verify_artifact_with_com(source,'excel',worker=UnsafeWorker())
    assert result['ok'] is False and 'policy' in result['error']


def test_source_links_and_casefold_collisions_leave_no_partial_candidate(tmp_path):
    source=tmp_path/'source';source.mkdir()
    (source/'skill.json').write_text('{}')
    destination=tmp_path/'candidate'
    with pytest.raises(ValueError,match='collision'):
        CandidateWorkspaceBuilder().export(source,destination,['skill.json'],{'Skill.json':'{}'})
    assert not destination.exists()


def test_source_hardlinks_are_not_exported(tmp_path):
    source=tmp_path/'source';source.mkdir()
    (source/'original.json').write_text('{}')
    os.link(source/'original.json',source/'skill.json')
    with pytest.raises(ValueError,match='one link'):
        CandidateWorkspaceBuilder().export(source,tmp_path/'candidate',['skill.json'],{})
