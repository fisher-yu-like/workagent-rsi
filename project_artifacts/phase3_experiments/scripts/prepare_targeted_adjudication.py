"""Build a separate follow-up page; never change a blind pack or generate labels."""
import argparse
import html
import json
import os
from pathlib import Path
import sys
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from workagent_rsi.hashing import sha256_file
from workagent_rsi.view_safety import ordinary_file, relative_reference

SCRIPT=r'''
const data=JSON.parse(document.getElementById('review-data').textContent);
document.getElementById('export').onclick=()=>{
 const reviewer=document.getElementById('reviewer').value.trim();
 if(!reviewer){alert('请填写姓名或昵称。');return;}
 const labels=[];
 for(const cid of data.case_ids){
  const label=document.getElementById('label-'+cid).value;
  const note=document.getElementById('note-'+cid).value.trim();
  const checked=document.getElementById('checked-'+cid).checked;
  if(!label||!checked||!note){alert('请完成每例的判断、核对确认和理由。无法确认时请选择 INCOMPLETE 并说明原因。');return;}
  labels.push({case_id:cid,reviewer_id:reviewer,label,defect_locations:[note],requirements_checked:true,timestamp:new Date().toISOString()});
 }
 const result={schema_version:'office-human-adjudication-v1',source_kind:'human_adjudication',
  rubric_hash:data.rubric_hash,source_submission_hash:data.source_submission_hash,
  request_manifest_hash:data.request_manifest_hash,adjudication_after_diagnostics:true,
  independent_blind_review:false,labels};
 const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));
 const link=document.createElement('a');link.href=url;link.download='office-human-adjudication.json';link.click();URL.revokeObjectURL(url);
};
'''


def prepare(pack,intake,notes_file,output):
    public=pack/'blind-review-pack'
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    review=read(public/'review-manifest.json');receipt=read(intake/'submission-receipt.json')
    if review['rubric_hash']!=receipt['rubric_hash']:raise ValueError('rubric changed')
    if sha256_file(intake/'external-submission.json')!=receipt['submission_hash']:
        raise ValueError('original human submission changed')
    labels={r['case_id']:r for r in [json.loads(line) for line in (intake/'human-labels.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]}
    notes=read(notes_file);cases={r['case_id']:r for r in review['cases']}
    if len({r['case_id'] for r in notes})!=len(notes):raise ValueError('duplicate follow-up case')
    pages={r['case_id']:r for r in read(public/'rendered-pages.json')}
    cards=[];bindings={};output=Path(output)
    def asset(name):
        path=ordinary_file(public/relative_reference(name));bindings[name]=sha256_file(path)
        return html.escape(quote(os.path.relpath(path,output).replace('\\','/'),safe='/.-_'),quote=True)
    for index,note in enumerate(notes,1):
        row=cases[note['case_id']];cid=row['case_id']
        if cid not in labels or row['cohort']!='standards-12':raise ValueError('follow-up requires an existing standard label')
        if sha256_file(public/row['artifact'])!=row['artifact_hash']:raise ValueError('artifact changed')
        links=' '.join(f'<a href="{asset(name)}">打开原输入 {i}</a>' for i,name in enumerate(row['inputs'],1))
        images=[]
        for page in pages[cid]['pages']:
            url=asset(page['file'])
            if bindings[page['file']]!=page['sha256']:raise ValueError('render page changed')
            images.append(f'<figure><figcaption>成品第 {page["page"]} 页</figcaption><img loading="lazy" src="{url}" alt="成品渲染页"></figure>')
        cards.append(f'''<article id="{cid}"><h2>{index}. {html.escape(row['domain'])} / {cid}</h2>
<h3>原任务说明</h3><pre>{html.escape(row['instruction'])}</pre>
<h3>本次重点核对</h3><p>{html.escape(note['focus'])}</p>
<p>你的初次标签：{html.escape(labels[cid]['label'])}。请自行核对后重新选择，页面没有预选答案。</p>
<p>{links} <a href="{asset(row['artifact'])}">打开成品原文件</a></p>{''.join(images)}
<p><label>复核判断 <select id="label-{cid}"><option value="">请选择</option><option value="PASS">PASS：所有明确要求均满足</option><option value="FAIL">FAIL：确认有不符合要求的缺陷</option><option value="PARTIAL">PARTIAL：部分完成</option><option value="INCOMPLETE">INCOMPLETE：证据不足或要求不清</option></select></label></p>
<p><label>核对依据、具体位置或无法确认的原因<br><textarea id="note-{cid}" rows="3"></textarea></label></p>
<p><label><input type="checkbox" id="checked-{cid}">我已对照任务说明、输入和成品核对本例；无法确认的内容已注明。</label></p></article>''')
    data={'case_ids':[r['case_id'] for r in notes],'rubric_hash':review['rubric_hash'],
        'source_submission_hash':receipt['submission_hash'],'asset_bindings':bindings}
    from workagent_rsi.hashing import canonical_json_hash
    data['request_manifest_hash']=canonical_json_hash(data)
    encoded=json.dumps(data,ensure_ascii=False).replace('<','\\u003c')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>六例人工复核</title>
<style>body{max-width:1050px;margin:24px auto;padding:0 18px;font:16px sans-serif;line-height:1.7}article{border-top:2px solid #bbb;margin-top:32px;padding-top:16px}pre{white-space:pre-wrap;background:#f3f5f7;padding:14px}img{max-width:100%;border:1px solid #ddd}textarea{width:95%}select,button,input{font-size:16px}figure{margin:18px 0}</style>
<h1>六个标准例的人工复核</h1><p>本页只复核有分歧的六例。每例先读原任务说明，再打开输入和成品。公式问题要查看公式；总数要对照明细计算。页面上的重点核对提示只是诊断线索，请根据材料自行判断。</p>
<p>PASS 表示所有明确要求都满足。确定有缺陷选 FAIL；部分完成选 PARTIAL；材料不足或要求含糊选 INCOMPLETE。请为每例写一句理由。</p>
<p>你已看过诊断提示，本轮属于复核裁定，不属于新的独立盲标。初次 32 条标签会保留，本页不会覆盖它们。页面不会联网或自动提交。</p>'''+''.join(cards)+'''
<section><h2>下载复核结果</h2><label>姓名或昵称 <input id="reviewer"></label> <button id="export">下载复核 JSON</button><p>下载文件名为 office-human-adjudication.json。完成后在聊天中告诉我保存路径。</p></section>
<script id="review-data" type="application/json">'''+encoded+'</script><script>'+SCRIPT+'</script></html>'
    output.mkdir(parents=True,exist_ok=False)
    (output/'index.html').write_text(page,encoding='utf-8')
    (output/'adjudication-request.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {'case_count':len(notes),'labels_generated':0,'independent_blind_review':False,
        'page':str(output/'index.html'),'request_manifest_hash':data['request_manifest_hash']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('pack','intake','notes','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.pack,args.intake,args.notes,args.output)))
