import json
from dataclasses import asdict
from pathlib import Path

import pytest

from workagent_rsi.contracts import TaskSpec
from workagent_rsi.hashing import sha256_file
from workagent_rsi.repeated_evaluation import evaluate_paired
from workagent_rsi.rsi_contracts import EvaluationContract
from workagent_rsi.statistical_promotion import ComparisonPolicy, RepeatedObservation, compare_repeated_runs


class RecordedExecutor:
    def __init__(self, cached=False):
        self.calls=[]
        self.cached=cached

    def evaluate_split(self, tasks, split, config, contract, root, **kwargs):
        self.calls.append((config,split,contract.repeats))
        root=Path(root);root.mkdir(parents=True)
        rows=[]
        for task in tasks:
            records=root/task.task_id/'provider_records'
            records.mkdir(parents=True)
            script=records/'script.py';script.write_text('print(42)',encoding='utf-8')
            digest=sha256_file(script)
            (records/'executed-scripts').mkdir()
            script.rename(records/'executed-scripts'/f'{digest}.py')
            (records/'tool_events.jsonl').write_text(json.dumps({'name':'run_python','result':{
                'script_sha256':digest,'script_snapshot_ref':f'executed-scripts/{digest}.py'}})+'\n',encoding='utf-8')
            score=.3 if config=='old' else .7
            row=dict(task_id=task.task_id, hidden_test=False, result_dir=str(records.parent),
                execution_complete=True, execution_success=True, task_outcome_complete=True,
                task_success=True, passed=True, assessment_complete=True, quality_score=score, score=score,
                score_report={'criterion_results':[]}, critical_requirements=[],
                telemetry={'semantic':[{'model_calls':0 if self.cached else 1}]})
            rows.append({**row,'repeats':[row]})
        report=dict(rows=rows, split=split, task_count=len(tasks), task_denominator=len(tasks),
            assessment_complete=True, task_outcomes_complete=True, assessment_identity='e',split_hash='x',evaluation_seconds=1)
        (root/'evaluation_full.json').write_text(json.dumps(report),encoding='utf-8')


def setup_contract():
    batches={s:[TaskSpec(task_id=f'{s}-{d}', domain=d, instruction='Produce an artifact')
                for d in ('excel','word','powerpoint')] for s in ('develop','regression','hidden','ood_transfer')}
    contract=EvaluationContract(contract_id='paired', dataset_hash='x',split_hashes={},evaluator_hash='e',
        provider_policy='p', seeds=[1],repeats=3,timeout_seconds=1,thresholds={},git_commit='test',
        comparison_policy=asdict(ComparisonPolicy(paired_resamples=100,min_families=2)),
        task_families={t.task_id:t.task_id for batch in batches.values() for t in batch})
    return batches,contract


def test_interleaving_keeps_every_repeat_and_never_grants_research(tmp_path):
    batches,contract=setup_contract();executor=RecordedExecutor()
    old,new,result=evaluate_paired(executor,batches,'old','new',contract,tmp_path)
    assert [executor.calls[i][0] for i in range(0,24,4)]==['old','new','new','old','old','new']
    assert all(call[2]==1 for call in executor.calls)
    assert result['eligible'] and result['research_qualified'] is False
    assert new['develop']['repeated_observation_count']==9
    assert new['develop']['quality_score']==pytest.approx(.7)
    assert result['execution_seed']=='not_supported'
    assert new['develop']['judge_variance'] is None
    with pytest.raises(FileExistsError):
        evaluate_paired(executor,batches,'old','new',contract,tmp_path)


def test_cached_judgement_cannot_enable_promotion(tmp_path):
    batches,contract=setup_contract()
    _,_,report=evaluate_paired(RecordedExecutor(cached=True),batches,'old','new',contract,tmp_path)
    assert not report['eligible']
    assert 'unqualified_quality_evidence' in report['splits']['develop']['blockers']


def test_success_metric_counts_artifact_failures_too():
    def rows(side):
        return [RepeatedObservation(str(i),str(i),'excel',r,f'{side}-{i}-{r}',True,
                    not (side=='old' and i==0),None,False,None,'p',
                    task_succeeded=side=='new') for i in range(3) for r in range(3)]
    report=compare_repeated_runs(rows('old'),rows('new'),ComparisonPolicy(paired_resamples=100,min_families=2))
    assert report['primary_metric']=='task_success_rate'
    assert report['effect']==1
