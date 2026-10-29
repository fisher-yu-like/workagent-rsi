"""Two explicitly bounded, hash-bound Office renders; defaults stay unchanged."""
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from workagent_rsi.apptainer_sandbox import ApptainerPolicy, ApptainerSSHExecutor
from workagent_rsi.artifact_renderer import RenderPolicy
from workagent_rsi.hashing import sha256_file


def recover(public, prior_worker_root, output):
    cases=json.loads((public/'review-manifest.json').read_text(encoding='utf-8'))['cases']
    ids={'review-c0ea6a3781224c9e':48,'review-2e562d78e43f4a93':96}
    if output.exists():raise FileExistsError(output)
    output.mkdir(parents=True)
    results=[]
    for row in cases:
        if row['case_id'] not in ids:continue
        source=public/row['artifact'];digest=sha256_file(source)
        if digest!=row['artifact_hash']:raise ValueError('original artifact changed')
        prior=next(p.parent.parent for p in prior_worker_root.glob('*/inputs/render-policy.json')
                   if json.loads(p.read_text(encoding='utf-8'))['source_sha256']==digest)
        trace=next((prior/'provider_records/sandbox').glob('*.json'))
        old=json.loads(trace.read_text(encoding='utf-8'))
        if not old['cleanup']['confirmed_absent'] or not old['resource_observations']['passed']:
            raise ValueError('previous worker boundary not established')
        policy=ApptainerPolicy.model_validate(old['policy'])
        work=output/row['case_id'];(work/'inputs').mkdir(parents=True)
        shutil.copyfile(source,work/'inputs/artifact.xlsx')
        config={'domain':'excel','source':'inputs/artifact.xlsx','source_sha256':digest,
                'dpi':96,'max_pages':100,'policy':RenderPolicy().model_dump(mode='json')}
        (work/'inputs/render-policy.json').write_text(json.dumps(config),encoding='utf-8')
        script=work/'render_office.py';script.write_bytes((ROOT/'src/workagent_rsi/libreoffice_worker.py').read_bytes())
        entry={'case_id':row['case_id'],'artifact_sha256':digest,'status':'reserved',
               'prior_trace_sha256':sha256_file(trace),'expected_pages':ids[row['case_id']],
               'max_pages':100,'dpi':96,'timeout_seconds':180,'policy':policy.model_dump(mode='json')}
        results.append(entry)
        (output/'recovery.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
        outcome=ApptainerSSHExecutor(policy).run(script,work,180)
        entry['outcome']=outcome.model_dump(mode='json')
        if outcome.status!='succeeded':
            entry['status']='unavailable'
        else:
            meta=json.loads((work/'outputs/render-metadata.json').read_text(encoding='utf-8'))
            if (meta.get('status')!='available' or meta.get('source_sha256')!=digest
                    or meta.get('owned_cleanup') is not True or len(meta.get('pages',[]))!=ids[row['case_id']]):
                raise ValueError('incomplete actual render or changed pagination')
            from PIL import Image
            pages=[]
            for number,p in enumerate(meta['pages'],1):
                image=work/p['file']
                if p['file']!=f'outputs/page-{number}.png' or sha256_file(image)!=p['sha256']:
                    raise ValueError('render reference/hash mismatch')
                with Image.open(image) as im:
                    if im.format!='PNG' or im.width*im.height>50_000_000:raise ValueError('image outside budget')
                    width,height=im.size
                pages.append({'page':number,'path':str(image.resolve()),'sha256':p['sha256'],'width':width,'height':height})
            entry.update(status='available',pages=pages,metadata_sha256=sha256_file(work/'outputs/render-metadata.json'))
        if sha256_file(source)!=digest or sha256_file(work/'inputs/artifact.xlsx')!=digest:
            raise ValueError('render modified source')
        (output/'recovery.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'case_id':entry['case_id'],'status':entry['status'],'pages':len(entry.get('pages',[]))}),flush=True)
        if entry['status']!='available':break
    return results


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['public','prior-worker-root','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();recover(a.public,a.prior_worker_root,a.output)
