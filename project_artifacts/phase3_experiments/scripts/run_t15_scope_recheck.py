"""Three-request real regression check for the corrected visual batch scope."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys

REPO=next(p for p in Path(__file__).resolve().parents if (p/'pyproject.toml').is_file())
sys.path.insert(0,str(REPO/'src'))
from qualification_cli import QualificationCLI
from run_t15_t16_judge_probe import FrozenRealRenderings,requirement,write
from workagent_rsi.hashing import sha256_file
from workagent_rsi.judgement_provider import VisualAssessmentChannel
from workagent_rsi.model_judgement import ModelJudgementProvider,ModelReviewConfig


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-policy',required=True,type=Path)
    parser.add_argument('--render-root',required=True,type=Path)
    options=parser.parse_args()
    runner=QualificationCLI(options.live_policy)
    root=REPO/'project_artifacts/results/hardening-v2/T15-scope-real'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    root.mkdir(parents=True)
    provider=ModelJudgementProvider(ModelReviewConfig(provider='codex-cli',model='gpt-6.1-sol',retries=0,
        repeats=1,timeout_seconds=90,cache_enabled=False),runner=runner)
    batches=[]
    class Capture:
        def identity_config(self):return provider.identity_config()
        def judge(self,request,work):
            decision,telemetry=provider.judge(request,work)
            batches.append({'selected_pages':request['batch_scope']['selected_pages'],
                'status':decision.status if decision else None,'model_calls':telemetry.get('model_calls'),
                'observed':decision.observed if decision else telemetry.get('error')})
            return decision,telemetry
    channel=VisualAssessmentChannel(FrozenRealRenderings(options.render_root),Capture(),root/'judges',
        max_images_per_check=8,cache_enabled=False)
    path=options.render_root/'sources/long-17.pptx'
    req=requirement('long-all-pages','The exact message "Required message: Revenue 25" must be fully visible and readable on every selected page.',
        'visual',pages=list(range(1,18)))
    started=datetime.now(timezone.utc).isoformat()
    result=channel.check(req,path,sha256_file(path),independent_review=True)
    expected=[list(range(1,9)),list(range(9,17)),[17]]
    passed=result['status']=='FAIL' and result['telemetry']['coverage']['complete'] and len(batches)==3
    passed=passed and [b['selected_pages'] for b in batches]==expected and [b['status'] for b in batches]==['PASS','PASS','FAIL']
    record={'status':'passed' if passed else 'failed','exit_code':0 if passed else 1,
        'started_at':started,'ended_at':datetime.now(timezone.utc).isoformat(),'command':[sys.executable,*sys.argv],
        'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'result':result,'batches':batches,
        'source_hashes':{p.name:sha256_file(p) for p in [Path(__file__),REPO/'src/workagent_rsi/judgement_provider.py']},
        'render_manifest_sha256':sha256_file(options.render_root/'visual/real-render-manifest.json')}
    write(root/'run.json',record)
    print(json.dumps({'evidence':str(root.relative_to(REPO)),'status':record['status'],'batches':batches}))
    return record['exit_code']


if __name__=='__main__':sys.exit(main())
