"""T20 fixed denominators and learning signals; no real model/server calls."""

from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import traceback

import pytest

from test_assessment_entrypoint_parity import (
    authored_spec,
    reviewed_task,
    book,
    ref,
    FixtureAssessment,
)
from workagent_rsi.artifact_assessment import spec_from_task
from workagent_rsi.harness_artifact_evaluator import HarnessArtifactEvaluator
from workagent_rsi.hashing import canonical_json_hash
from workagent_rsi.rsi_contracts import EvaluationContract
from workagent_rsi.rsi_feedback import build_feedback,comparison_metrics
from workagent_rsi.workagent_evaluator import WorkAgentFrozenEvaluator
from workagent_rsi.workagent_provider import WorkAgentConfig,WorkAgentSkill


def setup(tmp_path, names=("easy", "hard")):
    tasks = [
        reviewed_task(authored_spec().model_copy(update={"task_id": name}))
        for name in names
    ]
    cfg = WorkAgentConfig(verify_com=False)
    evaluator = WorkAgentFrozenEvaluator(
        workagent_config=cfg,
        input_base=tmp_path,
        assessment_output_root=tmp_path / "judge",
        assessment=FixtureAssessment(),
    )
    split_hash = canonical_json_hash([t.model_dump(mode="json") for t in tasks])
    contract = EvaluationContract(
        contract_id="authored-failure-feedback",
        dataset_hash=split_hash,
        split_hashes={"develop": split_hash},
        evaluator_hash=evaluator.evaluator_hash,
        assessment_mode="artifact-v1",
        assessment_identity=evaluator.assessment_identity,
        acceptance_hashes={t.task_id: spec_from_task(t).fingerprint() for t in tasks},
        provider_policy="workagent-config:"
        + canonical_json_hash(cfg.model_dump(mode="json")),
        seeds=[1],
        repeats=1,
        timeout_seconds=10,
        thresholds={},
        git_commit="authored-unit-fixture",
    )
    return tasks, evaluator, contract


def install_runs(monkeypatch,scenarios,calls):
    def run(harness,task,**kwargs):
        calls.append(task.task_id)
        scenario=scenarios[task.task_id]
        root=Path(harness.results_dir)/'run';root.mkdir(parents=True,exist_ok=True)
        if scenario in {'pass','artifact_fail'}:
            path=book(root,42 if scenario=='pass' else 7)
            result=HarnessArtifactEvaluator(root/'assessment',assessment=harness.assessment).evaluate(task,[ref(path)],'authored')
            return {'state':'SUCCEEDED' if result.passed else 'FAILED','artifacts':[ref(path).model_dump(mode='json')],
                'evaluation':result.model_dump(mode='json'),'result_dir':str(root)}
        origin=scenario if scenario in {'environment','model_transport','user_input'} else None if scenario=='unknown' else 'agent_execution'
        source='for value in [1,2]\n    print(value)\n'
        try:compile(source,'agent.py','exec')
        except SyntaxError as error:stderr=''.join(traceback.format_exception_only(type(error),error))
        digest=hashlib.sha256(source.encode()).hexdigest()
        records=root/'provider_records';snap=records/'executed-scripts';snap.mkdir(parents=True)
        (snap/(digest+'.py')).write_text(source,encoding='utf-8',newline='\n')
        event={'name':'run_python','arguments':{'path':'agent.py'},'result':{'ok':False,'stderr':stderr,
            'script_sha256':digest,'script_snapshot_ref':'executed-scripts/'+digest+'.py',
            'execution':{'status':'failed','failure_origin':'agent_execution'}}}
        (records/'tool_events.jsonl').write_text(json.dumps(event)+'\n')
        return {'state':'FAILED','artifacts':[],'result_dir':str(root),'failure':{
            'message':'SyntaxError: authored syntax failure' if origin=='agent_execution' else 'authored unavailable capability',
            'failure_origin':origin,'retryable':False,'status':'failure'}}
    monkeypatch.setattr('workagent_rsi.workagent_evaluator.Harness.run',run)


def evaluate(evaluator,tasks,contract,root,**options):
    return evaluator.evaluate_split(tasks,'develop',WorkAgentSkill(instructions='Use current inputs.'),contract,root,reveal_per_task=True,**options)


def test_syntax_failure_is_a_valid_zero_task_outcome_with_null_quality(tmp_path,monkeypatch):
    tasks,evaluator,contract=setup(tmp_path,('hard',));calls=[]
    install_runs(monkeypatch,{'hard':'agent_execution'},calls)
    report=evaluate(evaluator,tasks,contract,tmp_path/'split')
    assert report.get('execution_complete') is True and report.get('task_outcomes_complete') is True
    assert report['assessment_complete'] is False
    assert report['execution_success_rate']==report['task_success_rate']==0
    assert report['quality_score'] is None and report['quality_denominator']==0
    assert report['task_denominator']==1 and report['execution_failures']
    assert report['evaluation_seconds']>0,'failed executions must retain observed runtime cost'
    feedback=build_feedback(report)
    assert len(feedback.tasks)==1 and feedback.tasks[0]['quality_score'] is None
    assert 'SyntaxError' in feedback.model_dump_json()
    assert any('line 1' in d['causal_hypothesis'] for d in feedback.tasks[0]['diagnoses'])
    assert str(tmp_path) not in feedback.model_dump_json()
    (tmp_path/'failure-feedback.json').write_text(feedback.model_dump_json(indent=2))


@pytest.mark.parametrize('origin',['environment','model_transport','user_input','unknown'])
def test_infrastructure_or_unknown_failure_stops_without_zero_quality(tmp_path,monkeypatch,origin):
    tasks,evaluator,contract=setup(tmp_path);calls=[]
    install_runs(monkeypatch,{'easy':origin,'hard':'pass'},calls)
    report=evaluate(evaluator,tasks,contract,tmp_path/'split')
    assert report.get('execution_complete') is False and report.get('task_outcomes_complete') is False
    assert report.get('task_success_rate') is None and report['quality_score'] is None
    assert report.get('task_denominator')==2 and calls==['easy']
    assert not report.get('execution_failures')


def test_failed_hard_task_stays_in_denominator_and_has_no_visual_zero(
    tmp_path, monkeypatch
):
    tasks, evaluator, contract = setup(tmp_path)
    calls = []
    install_runs(monkeypatch, {"easy": "pass", "hard": "agent_execution"}, calls)
    report = evaluate(evaluator, tasks, contract, tmp_path / "split")
    assert (
        report.get("task_denominator") == 2 and report.get("task_success_rate") == 0.5
    )
    assert (
        report.get("execution_success_rate") == 0.5
        and report.get("quality_denominator") == 1
    )
    assert report["quality_score"] is None
    assert report["dimension_scores"] == {}
    assert report["evaluation_seconds"] == pytest.approx(
        sum(r["wall_time_seconds"] for r in report["rows"])
    )
    row = next(r for r in report["rows"] if r["task_id"] == "hard")
    assert row["quality_score"] is None and row["score_report"] is None
    assert row["telemetry"] == {} and row["task_success"] is False
    (tmp_path / "split-report.json").write_text(json.dumps(report, indent=2))


def test_artifact_failure_is_distinct_from_execution_failure(tmp_path, monkeypatch):
    tasks, evaluator, contract = setup(tmp_path, ("easy",))
    calls = []
    install_runs(monkeypatch, {"easy": "artifact_fail"}, calls)
    report = evaluate(evaluator, tasks, contract, tmp_path / "split")
    assert (
        report.get("execution_success_rate") == 1
        and report.get("task_success_rate") == 0
    )
    assert report["quality_score"] == 0.2 and report["assessment_complete"] is True
    assert not report.get("execution_failures")


def test_candidate_cannot_gain_quality_by_dropping_a_hard_task(tmp_path,monkeypatch):
    tasks,evaluator,contract=setup(tmp_path);calls=[]
    install_runs(monkeypatch,{'easy':'pass','hard':'pass'},calls)
    baseline=evaluate(evaluator,tasks,contract,tmp_path/'baseline/develop')
    install_runs(monkeypatch,{'easy':'pass','hard':'agent_execution'},calls)
    candidate=evaluate(evaluator,tasks,contract,tmp_path/'candidate/develop')
    metrics=comparison_metrics({'develop':baseline},{'develop':candidate},tmp_path,contract)
    assert metrics.get('task_comparable') is True and metrics['success_delta']==-.5
    assert metrics['quality_delta'] is None and metrics.get('paired_quality_delta')==0
    assert metrics.get('paired_quality_denominators')=={'develop':1}
    with pytest.raises(ValueError,match='split hash'):evaluate(evaluator,tasks[:1],contract,tmp_path/'dropped')


def test_private_execution_trace_is_absent_from_public_failure_feedback(tmp_path,monkeypatch):
    tasks,evaluator,contract=setup(tmp_path,('SECRET_HIDDEN',));calls=[]
    tasks=[tasks[0].model_copy(update={'hidden_test':True})]
    contract=contract.model_copy(update={'split_hashes':{'develop':canonical_json_hash([t.model_dump(mode='json') for t in tasks])}})
    # Admission fingerprint changes with hidden metadata; use the explicit legacy
    # profile for this visibility-only fixture, never claiming task acceptance.
    evaluator.assessment_profile='legacy'
    contract=contract.model_copy(update={'acceptance_hashes':{tasks[0].task_id:spec_from_task(tasks[0],assessment_profile='legacy').fingerprint()}})
    install_runs(monkeypatch,{'SECRET_HIDDEN':'agent_execution'},calls)
    report=evaluate(evaluator,tasks,contract,tmp_path/'split')
    assert not report.get('execution_failures') and 'SECRET_HIDDEN' not in json.dumps(report)


def test_provider_origin_survives_adapter_and_orchestrator(tmp_path,monkeypatch):
    from workagent_rsi.harness import Harness
    from workagent_rsi.workagent_provider import ProviderOutcome
    assert 'failure_origin' in ProviderOutcome.model_fields,'ProviderOutcome loses typed failure origin'
    monkeypatch.setattr('workagent_rsi.workagent_office.CodexOfficeProvider.run',lambda *a:ProviderOutcome(
        status='failed',failure_origin='agent_execution',error='authored invalid response'))
    tasks,_,_=setup(tmp_path,('easy',))
    result=Harness(tmp_path/'runs',execution_provider='workagent',workagent_config=WorkAgentConfig(verify_com=False)).run(tasks[0])
    assert result['failure'].get('failure_origin')=='agent_execution'


def test_missing_manifest_is_an_agent_execution_failure(tmp_path,monkeypatch):
    from workagent_rsi.harness import Harness
    from workagent_rsi.workagent_provider import ProviderOutcome,AgentResponse
    monkeypatch.setattr('workagent_rsi.workagent_office.CodexOfficeProvider.run',lambda *a:ProviderOutcome(status='completed',
        response=AgentResponse(status='completed',deliverables=['outputs/answer.xlsx'],summary='authored',input_files_used=[])))
    tasks,_,_=setup(tmp_path,('easy',))
    result=Harness(tmp_path/'runs',execution_provider='workagent',workagent_config=WorkAgentConfig(verify_com=False)).run(tasks[0])
    assert result['failure'].get('failure_origin')=='agent_execution'


def test_api_auth_failure_is_transport_not_zero_quality(tmp_path,monkeypatch):
    import urllib.error
    from workagent_rsi.workagent_provider import CodexOfficeProvider
    monkeypatch.setenv('OPENAI_API_KEY','AUTHORED_TEST_KEY_NOT_REAL')
    def rejected(*a,**k):raise urllib.error.HTTPError('https://example.invalid',401,'authored unauthorized',{},None)
    monkeypatch.setattr('urllib.request.urlopen',rejected)
    workspace=tmp_path/'workspace';workspace.mkdir()
    outcome=CodexOfficeProvider(WorkAgentConfig(backend='openai-chat',verify_com=False)).run('authored request',workspace,tmp_path/'records')
    assert getattr(outcome,'failure_origin',None)=='model_transport'


def test_rsi_reaches_candidate_generation_after_valid_code_failure(tmp_path,monkeypatch):
    from workagent_rsi.rsi_loop import RSILoop
    from workagent_rsi.registry import SkillRegistry
    from workagent_rsi.candidate_workspace import CandidateWorkspaceBuilder
    from workagent_rsi.promotion import PromotionController
    from workagent_rsi.verifier import CandidateVerifier,VerificationPolicy
    from workagent_rsi.rsi_contracts import ProviderRecord
    tasks,evaluator,contract=setup(tmp_path,('hard',));calls=[]
    install_runs(monkeypatch,{'hard':'agent_execution'},calls)
    package=WorkAgentSkill(instructions='Use current inputs.').model_dump(mode='json')
    registry=SkillRegistry(tmp_path/'registry')
    registry.register(skill_id='sum',version='1.0.0',package=package,manifest={'domain':'office'},parent_version=None,
        candidate_id=None,status='champion',evidence_refs=['a'*64])
    source=tmp_path/'source';source.mkdir();(source/'skill.json').write_text(json.dumps(package))
    seen=[]
    class Capture:
        def generate_with_context(self,context,workspace,records):
            seen.append(context)
            now=datetime.now(timezone.utc)
            return None,ProviderRecord(provider='authored-capture-no-model',provider_version='1',command=[],
                prompt_hash=context.fingerprint(),workspace_hash=context.champion_hash,started_at=now,ended_at=now,
                status='failed',error='Authored capture stops before proposing a candidate.')
    loop=RSILoop(registry=registry,workspace_builder=CandidateWorkspaceBuilder(),provider=Capture(),
        verifier=CandidateVerifier(),evaluator=evaluator,promotion=PromotionController(),skill_model=WorkAgentSkill)
    result=loop.run_round(skill_id='sum',tasks_by_split={'develop':tasks},contract=contract,source_root=source,
        run_root=tmp_path/'round',verification_policy=VerificationPolicy(allowed_targets={'skill.json'}))
    assert len(seen)==1 and seen[0].develop_feedback.tasks[0]['quality_score'] is None
    assert seen[0].diagnoses and 'SyntaxError' in seen[0].model_dump_json()
    assert result['champion_before']['content_hash']==result['champion_after']['content_hash']


@pytest.mark.parametrize('change,expected',[('staged','agent_execution'),('original','environment')])
def test_input_integrity_distinguishes_candidate_mutation_from_external_change(tmp_path,monkeypatch,change,expected):
    from workagent_rsi.harness import Harness
    from workagent_rsi.contracts import TaskSpec
    from workagent_rsi.workagent_provider import ProviderOutcome
    original=book(tmp_path)
    task=TaskSpec(task_id='edit-input',domain='excel',instruction='Edit the supplied input.',input_files=(str(original),))
    def mutate(provider,prompt,workspace,records):
        path=original if change=='original' else next((workspace/'inputs').glob('*.xlsx'))
        path.write_bytes(b'authored mutation')
        return ProviderOutcome(status='failed',failure_origin='agent_execution',error='authored')
    monkeypatch.setattr('workagent_rsi.workagent_office.CodexOfficeProvider.run',mutate)
    result=Harness(tmp_path/'runs',execution_provider='workagent',input_base=tmp_path,
        workagent_config=WorkAgentConfig(verify_com=False)).run(task)
    assert result['failure']['failure_origin']==expected


def test_executed_script_snapshot_survives_a_later_rewrite(tmp_path):
    from workagent_rsi.run_contracts import ExecutionOutcome
    from workagent_rsi.workagent_provider import _execute_native_tool
    workspace=tmp_path/'workspace';workspace.mkdir()
    source='for value in [1,2]\n    print(value)\n'
    script=workspace/'agent.py';script.write_text(source,encoding='utf-8',newline='\n')
    class AuthoredBoundary:
        def run(self,script,workspace,timeout):
            trace=workspace/'provider_records/sandbox/probe.json';trace.parent.mkdir(parents=True)
            trace.write_text('{"returncode":1,"stderr":"SyntaxError: authored"}')
            script.write_text('# rewritten after this execution\n')
            return ExecutionOutcome(status='failed',failure_origin='agent_execution',trace_refs=['provider_records/sandbox/probe.json'])
    records=tmp_path/'records'
    result=_execute_native_tool('run_python',{'path':'agent.py'},workspace,sandbox=AuthoredBoundary(),records=records)
    assert result['ok'] is False
    snapshot=records/result['script_snapshot_ref']
    assert snapshot.read_bytes()==source.encode() and hashlib.sha256(snapshot.read_bytes()).hexdigest()==result['script_sha256']
    assert script.read_bytes()!=snapshot.read_bytes()


def test_agent_script_timeout_is_valid_failure_but_transport_timeout_is_not(tmp_path,monkeypatch):
    from workagent_rsi.run_contracts import execution_from_legacy
    for origin,expected in [('agent_execution',True),('model_transport',False)]:
        outcome=execution_from_legacy({'state':'FAILED','failure':{'status':'timeout','failure_origin':origin}})
        assert outcome.status=='timeout' and (outcome.failure_origin=='agent_execution') is expected


def test_tampered_private_task_rows_cannot_shrink_comparison_denominator(tmp_path,monkeypatch):
    tasks,evaluator,contract=setup(tmp_path);calls=[]
    install_runs(monkeypatch,{'easy':'pass','hard':'pass'},calls)
    baseline=evaluate(evaluator,tasks,contract,tmp_path/'baseline/develop')
    candidate=evaluate(evaluator,tasks,contract,tmp_path/'candidate/develop')
    path=tmp_path/'candidate/develop/evaluation_full.json';data=json.loads(path.read_text());data['rows']=data['rows'][:1]
    path.write_text(json.dumps(data))
    metrics=comparison_metrics({'develop':baseline},{'develop':candidate},tmp_path,contract)
    assert metrics['task_comparable'] is False and metrics['comparable'] is False


@pytest.mark.parametrize('change',[{'quality_denominator':1},{'task_success_rate':.5}])
def test_public_metrics_must_agree_with_persisted_task_observations(tmp_path,monkeypatch,change):
    tasks,evaluator,contract=setup(tmp_path);calls=[]
    install_runs(monkeypatch,{'easy':'pass','hard':'pass'},calls)
    baseline=evaluate(evaluator,tasks,contract,tmp_path/'baseline/develop')
    candidate=evaluate(evaluator,tasks,contract,tmp_path/'candidate/develop')
    candidate.update(change)
    metrics=comparison_metrics({'develop':baseline},{'develop':candidate},tmp_path,contract)
    assert metrics['task_comparable'] is False and metrics['comparable'] is False
