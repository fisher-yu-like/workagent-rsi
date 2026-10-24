"""T23 production prompts use current requests, never pilot answer templates."""
import inspect

import pytest

from workagent_rsi.contracts import TaskSpec
from workagent_rsi.workagent_office import build_task_prompt, _task_mode


@pytest.mark.parametrize('domain',['excel','word','powerpoint'])
def test_task_id_suffix_cannot_change_strategy(domain):
    task=TaskSpec(task_id='arbitrary-create',domain=domain,instruction='Edit the supplied source.',input_files=('source',))
    other=task.model_copy(update={'task_id':'random-edit'})
    assert _task_mode(task)==_task_mode(other)=='edit'
    assert build_task_prompt(task,{'files':[]},'same skill')==build_task_prompt(other,{'files':[]},'same skill')


@pytest.mark.parametrize('domain',['excel','word','powerpoint'])
def test_prompt_has_no_fixture_answers(domain):
    prompt=build_task_prompt(TaskSpec(task_id='new',domain=domain,instruction='Use the current request.'),{'files':[]},'General skill')
    for text in ['Summary','120','150','180','Executive Summary','Completed Work','12 September',
                 'steering group','slide1 =','Takeaway: approve','Context and Plan','frozen three-slide','first tool call must']:
        assert text not in prompt
    assert {'excel':'load_workbook','word':'add_heading','powerpoint':'text_frame'}[domain] in prompt


def test_authorized_new_slide_is_not_forbidden_in_edit():
    task=TaskSpec(task_id='any',domain='powerpoint',instruction='Append two new slides to the source deck.',input_files=('source.pptx',))
    prompt=build_task_prompt(task,{'files':[]},'')
    assert 'never call add_slide' not in prompt and 'do not call presentation.slides.add_slide' not in prompt
    assert 'unless explicitly requested' in prompt or 'when requested' in prompt


def test_explicit_mode_can_create_from_inputs_and_is_bound_to_task_context():
    assert 'execution_mode' in TaskSpec.model_fields, 'T23 explicit execution mode is absent'
    from workagent_rsi.requirement_coverage import task_context
    task=TaskSpec(task_id='misleading-edit',domain='excel',instruction='Create a new analysis from the source.',input_files=('a.xlsx',),execution_mode='create')
    assert _task_mode(task)=='create' and task_context(task)['execution_mode']=='create'


def test_prompt_substitution_does_not_reinterpret_user_braces():
    task=TaskSpec(task_id='x',domain='word',instruction='Keep literal {format_rules} and {agent_instructions}.')
    prompt=build_task_prompt(task,{'files':[]},'champion')
    assert task.instruction in prompt


def test_explicit_authorized_template_is_preserved_without_hidden_answers():
    task=TaskSpec(task_id='x',domain='excel',instruction='Use the supplied worksheet template and retain its style.')
    prompt=build_task_prompt(task,{'files':[{'copied':'inputs/template.xlsx','copy_sha256':'a'*64,'source':'PRIVATE','hidden_expected':'PRIVATE'}]},'Use reusable library operations.')
    assert 'inputs/template.xlsx' in prompt and 'a'*64 in prompt and 'PRIVATE' not in prompt


def test_fixed_implementations_are_labelled_and_formal_runner_rejects_them(tmp_path,monkeypatch):
    from workagent_rsi.skill_runtime import SkillConfiguredOfficeAdapter
    from workagent_rsi.candidate_provider import DeterministicCandidateProvider
    from workagent_rsi.artifact_candidate import ArtifactFeedbackProvider
    from workagent_rsi.workagent_experiment import WorkAgentExperimentRunner
    from workagent_rsi.workagent_provider import WorkAgentSkill
    from workagent_rsi.experiment_runner import ExperimentRunner
    assert getattr(SkillConfiguredOfficeAdapter,'qualification_only',False) is True
    assert getattr(DeterministicCandidateProvider,'qualification_only',False) is True
    assert ArtifactFeedbackProvider.qualification_only is True
    assert getattr(ExperimentRunner,'qualification_only',False) is True
    runner=WorkAgentExperimentRunner()
    assert 'mode' in inspect.signature(runner.run).parameters
    with pytest.raises(ValueError,match='qualification_only'):
        runner.run({},WorkAgentSkill(instructions='general'),ArtifactFeedbackProvider(),tmp_path/'never',mode='formal')
    assert not (tmp_path/'never').exists()


def test_legacy_matrix_cannot_label_its_pilot_evaluator_as_formal(tmp_path,monkeypatch):
    from test_formal_runner import _load_runner
    runner=_load_runner()
    monkeypatch.setattr(runner,'validate_formal_gate',lambda *a,**k:{'ready':True})
    with pytest.raises(ValueError,match='qualification_only'):
        runner.run_matrix(mode='formal',provider_name='deterministic',experiments=['E01'],output_root=tmp_path/'never')
    assert not (tmp_path/'never').exists()
