import argparse,importlib.util,json,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from workagent_rsi.hashing import canonical_json_hash,sha256_file
from workagent_rsi.semantic_assessment import SemanticJudgement,validate_semantic_evidence,source_coverage_complete
from workagent_rsi.judgement_provider import VisualJudgement

p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--final',action='store_true');a=p.parse_args()
root=Path('project_artifacts/results/hardening-v2/T28-natural-judge/20261028')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
plan=read(root/'prepared-cjk-v3/manifest.json');data=read(a.results);effective={r['call_id']:r for r in data['effective_rows']}
path=Path('project_artifacts/phase3_experiments/scripts/prepare_natural_recovery.py');spec=importlib.util.spec_from_file_location('fixed_formatter',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
overrides={}
for folder in ['prepared-completion-v4','prepared-final-two','prepared-final-one']:
    proposal=read(root/folder/'proposal.json')
    for c in proposal['calls']:overrides[c['call_id']]=(c,root/folder)
count=0
for call in plan['calls']:
    row=effective[call['call_id']]
    if row['decision'] is None:continue
    if call['call_id'] in overrides and row['sha256']==overrides[call['call_id']][0]['sha256']:
        template,folder=overrides[call['call_id']]
        # A local template is identical; consistency templates have an explicit literal-format marker.
        request=read(folder/template['request'])
    else:request=read(root/'prepared-cjk-v3'/call['request'])
    if call['parents']:
        if request.get('parent_report_encoding'):
            encode=lambda d:mod.literal_report(d)
        else:encode=lambda d:json.dumps(d,ensure_ascii=False,separators=(',',':'))
        request['evidence']['items']=[{'evidence_id':cid,'location':{'artifact':'output'},'text':encode(effective[cid]['decision'])} for cid in call['parents']]
    assert canonical_json_hash(request)==row['actual_request_hash'],call['call_id']
    if call['modality']=='semantic':
        decision=SemanticJudgement.model_validate(row['decision']);validate_semantic_evidence(decision,request)
        if decision.status!='NEEDS_REVIEW':
            assert {o.evidence_id for o in decision.observations}=={i['evidence_id'] for i in request['evidence']['items']}
            assert source_coverage_complete(decision,request)
    else:
        decision=VisualJudgement.model_validate(row['decision']);images={i['image_id']:i['artifact_location'] for i in request['images']}
        assert all(images.get(o.image_id)==o.artifact_location for o in decision.observations)
        if decision.status!='NEEDS_REVIEW':assert {o.image_id for o in decision.observations}==set(images)
    count+=1
for path,digest in plan['input_bindings'].items():assert sha256_file(Path(path))==digest,path
if a.final:assert count==92
print('Verified effective decisions:',count,'request hashes, exact citations, coverage, and original file/page hashes')
