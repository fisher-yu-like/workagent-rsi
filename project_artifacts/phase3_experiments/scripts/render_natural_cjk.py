"""Render four CJK outputs with a read-only task font; base runtime unchanged."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from workagent_rsi.apptainer_sandbox import ApptainerPolicy,ApptainerSSHExecutor
from workagent_rsi.artifact_renderer import RenderPolicy
from workagent_rsi.hashing import sha256_file

TARGETS={'review-f730abc3d56ac9f6','review-9e0e9f65e6b4c39c','review-9741b22fc5ad5268','review-85c3776978b97315'}
FONT_SHA='2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b'
FONT_CONFIG='''<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><include ignore_missing="no">/etc/fonts/fonts.conf</include><dir>/task/inputs/fonts</dir><cachedir>/task/scratch/font-cache</cachedir></fontconfig>'''
PRELUDE='''import os as _os,subprocess as _subprocess
_os.environ['FONTCONFIG_FILE']='/task/inputs/fontconfig.conf'
_font_probe=_subprocess.run(['fc-match','-f','%{file}',':charset=4e2d'],capture_output=True,text=True,check=True,timeout=15).stdout.strip()
if not _font_probe.startswith('/task/inputs/fonts/'):
    raise RuntimeError('Task CJK font was not selected')
'''
POSTLUDE='''
_meta_path=Path('outputs/render-metadata.json')
_meta=json.loads(_meta_path.read_text())
_meta.setdefault('environment',{}).update(task_cjk_font_sha256=sha('inputs/fonts/NotoSansCJKsc-Regular.otf'),task_fontconfig_sha256=sha('inputs/fontconfig.conf'),cjk_font_probe=_font_probe)
_meta_path.write_text(json.dumps(_meta,indent=2))
'''


def render(public,assets,policy_path,output):
    font=assets/'NotoSansCJKsc-Regular.otf'
    if sha256_file(font)!=FONT_SHA:raise ValueError('font hash differs')
    if output.exists():raise FileExistsError(output)
    policy=ApptainerPolicy.model_validate_json(policy_path.read_text(encoding='utf-8'))
    cases=[r for r in json.loads((public/'review-manifest.json').read_text(encoding='utf-8'))['cases'] if r['case_id'] in TARGETS]
    if len(cases)!=4:raise ValueError('four frozen CJK cases required')
    output.mkdir(parents=True);rows=[]
    for row in cases:
        source=public/row['artifact'];digest=sha256_file(source)
        if digest!=row['artifact_hash']:raise ValueError('original output changed')
        work=output/row['case_id'];(work/'inputs/fonts').mkdir(parents=True)
        shutil.copyfile(font,work/'inputs/fonts'/font.name)
        shutil.copyfile(assets/'LICENSE',work/'inputs/fonts/LICENSE')
        copied=work/'inputs'/('artifact'+source.suffix);shutil.copyfile(source,copied)
        (work/'inputs/fontconfig.conf').write_text(FONT_CONFIG,encoding='utf-8')
        config={'domain':row['domain'],'source':copied.relative_to(work).as_posix(),'source_sha256':digest,
                'dpi':96,'max_pages':40,'policy':RenderPolicy().model_dump(mode='json')}
        (work/'inputs/render-policy.json').write_text(json.dumps(config),encoding='utf-8')
        script=work/'render_with_task_font.py'
        script.write_text(PRELUDE+(ROOT/'src/workagent_rsi/libreoffice_worker.py').read_text(encoding='utf-8')+POSTLUDE,encoding='utf-8')
        entry={'case_id':row['case_id'],'artifact_sha256':digest,'status':'reserved','task_font_sha256':FONT_SHA}
        rows.append(entry);(output/'recovery.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
        outcome=ApptainerSSHExecutor(policy).run(script,work,180);entry['outcome']=outcome.model_dump(mode='json')
        if outcome.status!='succeeded':entry['status']='unavailable'
        else:
            meta=json.loads((work/'outputs/render-metadata.json').read_text(encoding='utf-8'))
            if meta.get('status')!='available' or meta.get('owned_cleanup') is not True or meta.get('source_sha256')!=digest:
                raise ValueError('CJK rendering incomplete')
            if meta['environment']['task_cjk_font_sha256']!=FONT_SHA:raise ValueError('font proof differs')
            from PIL import Image
            pages=[]
            for n,p in enumerate(meta['pages'],1):
                image=work/p['file']
                if p['page']!=n or p['file']!=f'outputs/page-{n}.png' or sha256_file(image)!=p['sha256']:raise ValueError('invalid page export')
                with Image.open(image) as im:
                    if im.format!='PNG' or im.width*im.height>50_000_000:raise ValueError('invalid image')
                    width,height=im.size
                pages.append({'page':n,'path':str(image.resolve()),'sha256':p['sha256'],'width':width,'height':height})
            entry.update(status='available',pages=pages,environment=meta['environment'])
        if sha256_file(source)!=digest or sha256_file(copied)!=digest:raise ValueError('workbook/document changed')
        (output/'recovery.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'case_id':row['case_id'],'status':entry['status'],'pages':len(entry.get('pages',[]))}),flush=True)
        if entry['status']!='available':break
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['public','assets','policy','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();render(a.public,a.assets,a.policy,a.output)
