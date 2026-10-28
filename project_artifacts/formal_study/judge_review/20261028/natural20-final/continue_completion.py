"""Controller resume of never-issued approved completion slots; no failed retry."""
import argparse,importlib.util,json,sys
from pathlib import Path
ROOT=Path.cwd();sys.path.insert(0,str(ROOT/'src'))
from workagent_rsi.hashing import sha256_file,canonical_json_hash
from workagent_rsi.model_judgement import ModelJudgementProvider
from workagent_rsi.run_contracts import LiveCallPolicy
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
p=argparse.ArgumentParser();p.add_argument('--previous',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
root=ROOT/'project_artifacts/results/hardening-v2/T28-natural-judge/20261028'
prepared=root/'prepared-completion-v4';policy_path=root/'approved-completion-v4/live-policy.json'
proposal=read(prepared/'proposal.json');receipt=read(policy_path.with_name('approval-receipt.json'))
assert proposal['proposal_hash']=='ed5a6ca903f28f80208de7754c50fd2c7a4a1c14ae85f297152d1ecb64dcc513'
assert canonical_json_hash({k:v for k,v in proposal.items() if k!='proposal_hash'})==proposal['proposal_hash']
assert receipt['approved_by_user'] is True and receipt['manifest_sha256']==sha256_file(prepared/'proposal.json') and receipt['policy_sha256']==sha256_file(policy_path)
for name,digest in {**proposal['input_bindings'],**proposal['execution_code_hashes']}.items():assert sha256_file(Path(name))==digest,name
for call in proposal['calls']:assert sha256_file(prepared/call['request'])==call['sha256']
policy=LiveCallPolicy.model_validate_json(policy_path.read_text(encoding='utf-8'));assert policy.max_model_calls==109 and policy.max_wall_seconds==7200 and policy.max_tool_calls==0
previous=read(a.previous);assert previous['proposal_hash']==proposal['proposal_hash']
rows=list(previous['rows']);assert rows and len(rows)<len(proposal['calls'])
for row,call in zip(rows,proposal['calls']):assert all(row[k]==v for k,v in call.items())
state=read(policy_path.with_name('budget-state.json'));assert not state.get('quarantined')
historical=read(Path(receipt['historical_budget_path']));assert sha256_file(Path(receipt['historical_budget_path']))==receipt['historical_budget_sha256']
assert state['calls'][:len(historical['calls'])]==historical['calls']
assert len(state['calls'])==len(historical['calls'])+sum(r['attempted'] for r in rows)
assert state['reserved_wall_seconds']>=historical['reserved_wall_seconds']
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
helper=load('frozen_recovery',ROOT/'project_artifacts/phase3_experiments/scripts/prepare_natural_recovery.py')
budget=load('frozen_cli',ROOT/'project_artifacts/phase3_experiments/scripts/qualification_cli.py')
aggregator=load('frozen_aggregate',ROOT/'project_artifacts/phase3_experiments/scripts/natural_judge.py')
provider=ModelJudgementProvider(proposal['model_config'],runner=budget.QualificationCLI(policy_path))
effective={r['call_id']:r for r in previous['effective_rows']};plan=read(Path(proposal['original_manifest']))
a.output.mkdir(parents=True,exist_ok=False)
for call in proposal['calls'][len(rows):]:
 request=read(prepared/call['request']);decision=None
 if call['parents'] and any(not effective[c]['decision'] for c in call['parents']):
  attempted=False;telemetry={'status':'unavailable','reason':'parent result missing;no model call'}
 else:
  if call['parents']:request['evidence']['items']=[{'evidence_id':c,'location':{'artifact':'output'},'text':helper.literal_report(effective[c]['decision'])} for c in call['parents']]
  decision,telemetry=provider.judge(request,a.output/call['call_id']);attempted=True
 row={**call,'decision':decision.model_dump(mode='json') if decision else None,'attempted':attempted,'telemetry':telemetry,'actual_request_hash':canonical_json_hash(request)}
 rows.append(row);effective[call['call_id']]=row
 statuses={cid:aggregator.aggregate([effective[c['call_id']]['decision'] for c in plan['calls'] if c['case_id']==cid]) for cid in {c['case_id'] for c in plan['calls']}}
 result={'proposal_hash':proposal['proposal_hash'],'rows':rows,'effective_rows':list(effective.values()),'declared_scope_results':statuses,'quality_qualified':False,
         'explicit_unissued_continuation':{'prior_results_sha256':sha256_file(a.previous),'failed_requests_retried':False,'controller_source_sha256':sha256_file(Path(__file__))}}
 (a.output/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'processed_completion_slots':len(rows),'cap':len(proposal['calls']),'call_id':call['call_id'],'attempted':attempted,'status':row['decision']['status'] if row['decision'] else None}),flush=True)
 if attempted and decision is None:break
