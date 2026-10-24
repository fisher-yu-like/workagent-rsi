"""Check actual RSI rejection using a frozen real behavior baseline.

The baseline reuses the actual parent Office artifacts in a previous T08 run.
This is a registry/verifier integration probe, not a full live RSI benchmark.
No new model requests are made. Candidate behavior is run again remotely.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys

REPO=next(p for p in Path(__file__).resolve().parents if (p/'pyproject.toml').is_file())
sys.path.insert(0,str(REPO/'src'))
from workagent_rsi.apptainer_sandbox import ApptainerPolicy,ApptainerSSHExecutor
from workagent_rsi.behavior_probe import FixedSandboxBehaviorProbe
from workagent_rsi.candidate_workspace import CandidateWorkspaceBuilder
from workagent_rsi.contracts import TaskSpec
from workagent_rsi.hashing import canonical_json_hash,sha256_file
from workagent_rsi.promotion import PromotionController
from workagent_rsi.registry import SkillRegistry
from workagent_rsi.rsi_contracts import CandidatePatch,AtomicEdit,EvaluationContract,ProviderRecord
from workagent_rsi.rsi_loop import RSILoop
from workagent_rsi.verifier import CandidateVerifier,VerificationPolicy
from workagent_rsi.workagent_provider import WorkAgentSkill


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--behavior-root',type=Path,required=True)
    options=parser.parse_args()
    original=options.behavior_root.resolve(strict=True)
    run=json.loads((original/'run.json').read_text())
    if run['status']!='passed':raise ValueError('actual passed behavior evidence required')
    root=REPO/'project_artifacts/results/hardening-v2/T08-rsi-real'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    root.mkdir(parents=True)
    packages=json.loads((original/'packages.json').read_text())
    taskset=json.loads((original/'fixed-taskset.json').read_text())
    traces=list((original/'behavior').glob('*/outputs/behavior.json'))
    records=[json.loads(p.read_text()) for p in traces]
    if not records or not all(all(row['parent_passed'] for row in r['rows']) for r in records):
        raise ValueError('actual parent behavior not successful')
    tasks=[TaskSpec(task_id=t['task_id'],domain='excel',instruction='Sum the complete current numeric input into Summary B2.') for t in taskset['tasks']]
    split_hash=canonical_json_hash([t.model_dump(mode='json') for t in tasks])
    parent=packages['parent']
    policy=ApptainerPolicy.model_validate_json((original/'sandbox-policy.json').read_text())
    program=original/'t08_fixed_behavior_program.py'
    probe=FixedSandboxBehaviorProbe(executor=ApptainerSSHExecutor(policy),program=program,program_sha256=sha256_file(program),
        taskset=original/'fixed-taskset.json',taskset_sha256=sha256_file(original/'fixed-taskset.json'),
        output_root=root/'behavior',qualification='isolated_run')
    candidate=CandidatePatch(candidate_id='bad-rsi',parent_version='1.0.0',provider='authored-regression-control',provider_version='1',
        diagnosis_refs=[canonical_json_hash(records)],edit_budget=1,created_at=datetime.now(timezone.utc),atomic_edits=[AtomicEdit(
            component='prompt',target_path='skill.json',patch=json.dumps({'instructions':packages['bad']['instructions']}),
            hypothesis='Authored first-two-rows regression control',expected_metric='fixed task acceptance')])
    class FixedCandidate:
        def generate(self,workspace,diagnoses,parent_version,edit_budget,record_root):
            now=datetime.now(timezone.utc)
            return candidate,ProviderRecord(provider='authored-regression-control',provider_version='1',command=['fixed-control-no-model'],
                prompt_hash=canonical_json_hash(candidate.model_dump(mode='json')),workspace_hash=canonical_json_hash(parent),
                started_at=now,ended_at=now,status='completed',exit_code=0)
    class ActualFrozenParent:
        def evaluate_split(self,selected,split,config,contract,result_root,**kw):
            if config.model_dump(mode='json')!=parent:raise ValueError('candidate must never reach evaluator')
            if canonical_json_hash([t.model_dump(mode='json') for t in selected])!=split_hash:raise ValueError('taskset changed')
            return {'split':split,'score':1.0,'rows':[{'task_id':t.task_id,'passed':True} for t in tasks],
                'evidence_refs':[sha256_file(p) for p in traces],'qualification_scope':'reused actual parent fixed-task behavior only'}
    registry=SkillRegistry(root/'registry')
    registry.register(skill_id='t08.sum',version='1.0.0',package=parent,manifest={'domain':'office'},
        parent_version=None,candidate_id=None,status='champion',evidence_refs=[canonical_json_hash(records)])
    source=root/'source';source.mkdir();(source/'skill.json').write_text(json.dumps(parent))
    contract=EvaluationContract(contract_id='authored-t08-registry-probe',dataset_hash=sha256_file(original/'fixed-taskset.json'),
        split_hashes={'develop':split_hash},evaluator_hash=canonical_json_hash(records),provider_policy='authored-frozen-generation',
        seeds=[1],repeats=1,timeout_seconds=90,thresholds={'develop_gain':.01,'max_cost_delta':1.0},git_commit=run['commit'])
    loop=RSILoop(registry=registry,workspace_builder=CandidateWorkspaceBuilder(),provider=FixedCandidate(),
        verifier=CandidateVerifier(behavior_probe=probe),evaluator=ActualFrozenParent(),promotion=PromotionController(),skill_model=WorkAgentSkill)
    result=loop.run_round(skill_id='t08.sum',tasks_by_split={'develop':tasks},contract=contract,source_root=source,
        run_root=root/'round',verification_policy=VerificationPolicy(allowed_targets={'skill.json'},timeout_seconds=90))
    passed=result['verification']['behavior_status']=='failed' and result['decision']['decision']=='reject'
    passed=passed and result['champion_before']['content_hash']==result['champion_after']['content_hash']==canonical_json_hash(parent)
    record={'status':'passed' if passed else 'failed','exit_code':0 if passed else 1,'command':[sys.executable,*sys.argv],
        'recorded_at':datetime.now(timezone.utc).isoformat(),'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'scope':__doc__,'original_behavior_root':str(original.relative_to(REPO)),
        'original_taskset_sha256':sha256_file(original/'fixed-taskset.json'),'script_sha256':sha256_file(Path(__file__)),
        'champion_unchanged':result['champion_before']['content_hash']==result['champion_after']['content_hash'],
        'verification':result['verification'],'decision':result['decision']}
    (root/'run.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'evidence':str(root.relative_to(REPO)),'status':record['status']}))
    return record['exit_code']


if __name__=='__main__':sys.exit(main())
