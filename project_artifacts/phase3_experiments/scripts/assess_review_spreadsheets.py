"""Check existing review workbooks with pinned native targets and fresh recalc.

This evaluator-side diagnostic never reads human labels, sends references to a
model or claims official-environment parity or whole-task admission.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from workagent_rsi.apptainer_sandbox import ApptainerPolicy, ApptainerSSHExecutor
from workagent_rsi.benchmark_scoring import score_spreadsheet
from workagent_rsi.hashing import sha256_file
from workagent_rsi.spreadsheet_recalc import RecalculationEngine
from workagent_rsi.view_safety import ordinary_file


def run(pack,plan_path,task_manifest,scorers_path,cache,policy_path,output,*,max_recalculations=30,max_seconds=600):
    output.mkdir(parents=True,exist_ok=False)
    public=pack/'blind-review-pack'
    review=json.loads((public/'review-manifest.json').read_text(encoding='utf-8'))
    keys=json.loads((pack/'evaluator-only/case-key.json').read_text(encoding='utf-8'))
    natural={r['original_id']:r['case_id'] for r in keys['cases'] if r['cohort']=='natural-blind'}
    published={r['case_id']:r for r in review['cases']}
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    source=json.loads(task_manifest.read_text(encoding='utf-8'))
    tasks={r['base_task_id']:r for r in source['tasks']}
    jobs=[j for j in plan['jobs'] if j['domain']=='excel' and j['case_id'] in natural]
    policy=ApptainerPolicy.model_validate_json(policy_path.read_text(encoding='utf-8'))
    engine=RecalculationEngine(sandbox=ApptainerSSHExecutor(policy),qualification='isolated_run',
                             timeout_seconds=90,output_root=output/'worker-evidence')
    scorers=json.loads(scorers_path.read_text(encoding='utf-8'))['scorers']
    memo={};attempts=0;started=time.monotonic();rows=[]
    def recalculate(path):
        nonlocal attempts
        digest=sha256_file(path)
        if digest in memo:return memo[digest]
        if attempts>=max_recalculations or max_seconds-(time.monotonic()-started)<120:
            return None,None
        attempts+=1
        target=output/'recalculated'/(digest+'.xlsx')
        result=engine.recalculate(path,target)
        # Policy identity is fixed per cohort. Never change the engine timeout
        # inside a comparable recalculation trio just to finish near a deadline.
        memo[digest]=(target,result.model_dump(mode='json'))
        return memo[digest]
    for job in jobs:
        case_id=natural[job['case_id']];task=tasks[job['base_task_id']]
        row={'case_id':case_id,'natural_id':job['case_id'],'base_task_id':task['base_task_id']}
        try:
            variant=next(v for v in task['variants'] if v['variant_id']==job['variant_id'])
            task={**task,'variants':[variant]}
            if len(variant['inputs'])!=1 or not variant.get('reference'):
                raise ValueError('native target source/reference unavailable')
            base=Path(source['roots'][task['benchmark']]);view=published[case_id]
            paths={'input':ordinary_file(base/variant['inputs'][0]['path']),
                   'reference':ordinary_file(base/variant['reference']['path']),
                   'output':ordinary_file(public/view['artifact'])}
            expected={'input':variant['inputs'][0]['sha256'],'reference':variant['reference']['sha256'],
                      'output':view['artifact_hash']}
            if any(sha256_file(p)!=expected[name] for name,p in paths.items()):
                raise ValueError('frozen input/reference/output hash changed')
            receipts={};recalculated={}
            # Keep a constant engine identity. If less than one complete
            # timeout remains, stop launching work rather than changing policy.
            for name,path in paths.items():
                target,receipt=recalculate(path)
                receipts[name]=receipt;recalculated[name]=target
            if any(r is None or r['status']!='available' for r in receipts.values()):
                row.update(status='unavailable',score=None,reason='One or more isolated recalculations unavailable',
                    recalculation={name:None if r is None else {k:v for k,v in r.items() if k!='values'} for name,r in receipts.items()})
            else:
                scorer=scorers[task['benchmark']]
                row.update(score_spreadsheet(task,scorer_path=cache/scorer['local_path'],scorer_sha256=scorer['sha256'],
                    sources=paths,recalculated=recalculated,receipts=receipts))
        except (OSError,ValueError,KeyError,TypeError) as exc:
            row.update(status='unavailable',score=None,reason=type(exc).__name__+': '+str(exc))
        rows.append(row)
        report={'scope':'Pinned native target checks under recorded LibreOffice, not official-environment parity or whole-task acceptance',
            'official_leaderboard_claim':False,'whole_task_admission':'NOT_ASSESSED','human_labels_read':False,
            'model_calls':0,'expected_workbooks':len(jobs),'completed_workbooks':len(rows),
            'recalculation_attempts':attempts,'max_recalculations':max_recalculations,'max_seconds':max_seconds,
            'actual_worker_jobs':len(list((output/'worker-evidence').glob('**/provider_records/sandbox/*.json'))),
            'wall_seconds':time.monotonic()-started,'rows':rows,'recorded_at':datetime.now(timezone.utc).isoformat()}
        (output/'native-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('pack','plan','task-manifest','scorers','cache','sandbox-policy','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    report=run(args.pack,args.plan,args.task_manifest,args.scorers,args.cache,args.sandbox_policy,args.output)
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}))
    return 0

if __name__=='__main__':raise SystemExit(main())
