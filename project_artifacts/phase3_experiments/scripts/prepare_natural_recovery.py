"""Prepare only missing natural-review channels; no live calls or label edits."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(Path(__file__).parent))
from workagent_rsi.hashing import canonical_json_hash,sha256_file


def literal_report(decision):
    """Flatten structured report fields into exact-citable original strings."""
    lines=[]
    def visit(value,path):
        if isinstance(value,dict):
            for key,item in value.items():visit(item,path+'.'+key)
        elif isinstance(value,list):
            for n,item in enumerate(value):visit(item,path+f'[{n}]')
        else:lines.extend([path, str(value) if value is not None else 'null','END FIELD'])
    visit(decision,'report')
    return '\n'.join(lines)


def prepare(prepared,results_path,output,*,allow_unissued=False,max_total_seconds=5400):
    if max_total_seconds not in {5400,7200}:raise ValueError('unsupported proposed time cap')
    plan=json.loads((prepared/'manifest.json').read_text(encoding='utf-8'))
    if canonical_json_hash({k:v for k,v in plan.items() if k!='manifest_hash'})!=plan['manifest_hash']:raise ValueError('original manifest changed')
    result=json.loads(results_path.read_text(encoding='utf-8'))
    if result['manifest_hash']!=plan['manifest_hash']:raise ValueError('wrong original cohort')
    rows=result['rows']
    if len(rows)>len(plan['calls']) or (len(rows)!=len(plan['calls']) and not allow_unissued):raise ValueError('finish all unissued original slots before freezing recovery')
    if any(any(row[k]!=call[k] for k in call) for row,call in zip(rows,plan['calls'])):raise ValueError('results differ from fixed manifest')
    processed=len(rows);valid=sum(row['decision'] is not None for row in rows)
    rows=rows+[{**call,'decision':None,'attempted':False,'telemetry':{'status':'not_issued'}} for call in plan['calls'][processed:]]
    if output.exists():raise FileExistsError(output)
    output.mkdir(parents=True);calls=[]
    for row in rows:
        if row['decision'] is not None:continue
        source=prepared/row['request']
        if sha256_file(source)!=row['sha256']:raise ValueError('original request changed')
        request=json.loads(source.read_text(encoding='utf-8'))
        if row['phase']=='consistency':
            request['evidence']['items']=[]
            request['parent_report_encoding']='literal fields; exact strings, no nested JSON escape layer'
        name=row['request'];(output/name).write_text(json.dumps(request,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        calls.append({'call_id':row['call_id'],'case_id':row['case_id'],'phase':row['phase'],
            'modality':row['modality'],'parents':row['parents'],'request':name,
            'sha256':sha256_file(output/name),'prior_attempted':row.get('attempted',True)})
    proposal={'schema_version':'natural-review-recovery-proposal-v1','allow_live_calls':False,
        'original_manifest_hash':plan['manifest_hash'],'original_results_sha256':sha256_file(results_path),
        'original_results':str(results_path.resolve()),'original_manifest':str((prepared/'manifest.json').resolve()),
        'original_manifest_sha256':sha256_file(prepared/'manifest.json'),'input_bindings':plan['input_bindings'],
        'execution_code_hashes':{str(p.resolve()):sha256_file(p) for p in [Path(__file__),Path(__file__).with_name('qualification_cli.py'),Path(__file__).with_name('natural_judge.py'),ROOT/'src/workagent_rsi/model_judgement.py']},
        'calls':calls,'max_new_calls':len(calls),
        'original_processed_slots':processed,'original_valid_decisions':valid,
        'unissued_slots':len(plan['calls'])-processed,'max_total_seconds':max_total_seconds,
        'model_config':plan['model_config'],'required_tools':0,'automatic_retries':0,
        'summary_encoding':'literal-report-fields-v1','successful_original_decisions_preserved':True,
        'failed_opinions_reused':False,'human_labels_included':False,'reference_answers_included':False,
        'scope':'Recover missing channels only;successes are not new independent samples.'}
    proposal['proposal_hash']=canonical_json_hash(proposal)
    (output/'proposal.json').write_text(json.dumps(proposal,indent=2)+'\n',encoding='utf-8')
    return proposal


def execute(prepared,policy_path,output):
    from workagent_rsi.model_judgement import ModelJudgementProvider
    from workagent_rsi.run_contracts import LiveCallPolicy
    from natural_judge import aggregate
    read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    proposal=read(prepared/'proposal.json')
    if canonical_json_hash({k:v for k,v in proposal.items() if k!='proposal_hash'})!=proposal['proposal_hash']:raise ValueError('recovery proposal changed')
    receipt=read(policy_path.with_name('approval-receipt.json'))
    if (receipt.get('approved_by_user') is not True or receipt['manifest_sha256']!=sha256_file(prepared/'proposal.json')
            or receipt['policy_sha256']!=sha256_file(policy_path)):raise ValueError('recovery approval mismatch')
    for key in ['original_results','original_manifest']:
        if sha256_file(Path(proposal[key]))!=proposal[key+'_sha256']:raise ValueError('original evidence changed')
    for name,digest in {**proposal['input_bindings'],**proposal['execution_code_hashes']}.items():
        if sha256_file(Path(name))!=digest:raise ValueError('frozen recovery input/code changed')
    for call in proposal['calls']:
        if sha256_file(prepared/call['request'])!=call['sha256']:raise ValueError('recovery request changed')
    old=read(Path(receipt['historical_budget_path']))
    if sha256_file(Path(receipt['historical_budget_path']))!=receipt['historical_budget_sha256']:raise ValueError('prior budget changed')
    state=read(policy_path.with_name('budget-state.json'))
    if state['calls']!=old['calls'] or state['reserved_wall_seconds']<old['reserved_wall_seconds']:raise ValueError('budget replay/reset forbidden')
    policy=LiveCallPolicy.model_validate_json(policy_path.read_text(encoding='utf-8'))
    if policy.max_model_calls>len(old['calls'])+proposal['max_new_calls'] or policy.max_wall_seconds>proposal['max_total_seconds'] or policy.max_tool_calls!=0:raise ValueError('recovery policy exceeds approved scope')
    if output.exists():raise FileExistsError(output)
    spec=importlib.util.spec_from_file_location('natural_recovery_cli',Path(__file__).with_name('qualification_cli.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    provider=ModelJudgementProvider(proposal['model_config'],runner=module.QualificationCLI(policy_path))
    originals=read(Path(proposal['original_results']));original_plan=read(Path(proposal['original_manifest']))
    effective={call['call_id']:{**call,'decision':None,'attempted':False,'telemetry':{'status':'not_issued'}} for call in original_plan['calls']}
    effective.update({r['call_id']:r for r in originals['rows']});results=[];output.mkdir(parents=True)
    for call in proposal['calls']:
        request=read(prepared/call['request']);decision=None;telemetry={}
        if call['parents'] and any(not effective[p]['decision'] for p in call['parents']):
            telemetry={'status':'unavailable','reason':'parent missing; no model call'};attempted=False
        else:
            if call['parents']:
                request['evidence']['items']=[{'evidence_id':p,'location':{'artifact':'output'},'text':literal_report(effective[p]['decision'])} for p in call['parents']]
            decision,telemetry=provider.judge(request,output/call['call_id']);attempted=True
        row={**call,'decision':decision.model_dump(mode='json') if decision else None,
            'attempted':attempted,'telemetry':telemetry,'actual_request_hash':canonical_json_hash(request)}
        results.append(row);effective[call['call_id']]=row
        statuses={cid:aggregate([effective[c['call_id']]['decision'] for c in original_plan['calls'] if c['case_id']==cid]) for cid in {c['case_id'] for c in original_plan['calls']}}
        (output/'results.json').write_text(json.dumps({'proposal_hash':proposal['proposal_hash'],'rows':results,
            'effective_rows':list(effective.values()),'declared_scope_results':statuses,'quality_qualified':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'new_recovery_attempts':sum(r['attempted'] for r in results),'case_id':call['case_id'],'decision':row['decision']['status'] if row['decision'] else None}),flush=True)
        if attempted and decision is None:break


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['prepared','results','output','policy']:p.add_argument('--'+name,type=Path)
    p.add_argument('--include-unissued',action='store_true')
    p.add_argument('--max-total-seconds',type=int,default=5400)
    a=p.parse_args()
    if a.policy:execute(a.prepared,a.policy,a.output)
    else:
        d=prepare(a.prepared,a.results,a.output,allow_unissued=a.include_unissued,max_total_seconds=a.max_total_seconds);print(json.dumps({'new_calls':d['max_new_calls'],'proposal_hash':d['proposal_hash']}))
