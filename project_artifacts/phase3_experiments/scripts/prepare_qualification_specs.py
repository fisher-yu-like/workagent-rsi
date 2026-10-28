"""Draft source-grounded T31 requirements without granting independent review.

Reads the frozen public task bundle and its inputs only. No candidate output,
gold answer, model, server or reviewer identity is used to choose requirements.
Unsupported obligations remain uncovered instead of receiving placeholder checks.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from workagent_rsi.assessment_contracts import AcceptanceSpec, Requirement, Location, RequirementInventory, TaskRequirement
from workagent_rsi.check_registry import validate_acceptance_spec
from workagent_rsi.hashing import canonical_json_hash, sha256_file
from workagent_rsi.requirement_coverage import admission_for_spec, task_fingerprint
from workagent_rsi.study_protocol import read_tasks
from workagent_rsi.view_safety import ordinary_file


def instruction_spans(instruction):
    """Lossless non-whitespace spans; these are draft units, not reviewed atoms."""
    spans=[]
    for line in re.finditer(r'[^\n]+',instruction):
        text=line.group()
        parts=[text] if re.match(r'\s*\d+\.\s+',text) else re.split(r'(?<=[.!?])\s+(?=[A-Z])',text)
        cursor=0
        for part in parts:
            offset=text.index(part,cursor);cursor=offset+len(part)
            quote=part.strip()
            if quote:
                start=line.start()+offset+len(part)-len(part.lstrip())
                spans.append({'source_quote':quote,'start':start,'end':start+len(quote)})
    covered={i for s in spans for i in range(s['start'],s['end'])}
    if any(not char.isspace() and i not in covered for i,char in enumerate(instruction)):
        raise ValueError('instruction segmentation lost source content')
    return spans


def route(domain,quote):
    """Conservative proposed routes based on current registered channel limits."""
    text=quote.lower()
    if domain=='powerpoint':
        if re.fullmatch(r'Save the result as output\.pptx\.', quote):
            return 'deterministic',None,None
        if any(term in text for term in ('editable','native','raster','flat slide')):
            return 'uncovered','native_object_editability','Package/object inspection must prove editable text/shapes/connectors and raster prohibition; a screenshot cannot establish these.'
        if 'output.pptx' in text:
            return 'uncovered','output_filename_binding','Format checks exist, but exact output filename must also be bound in runner artifact admission.'
        return 'uncovered','source_figure_comparison','Frozen source PNG/PDF must be jointly compared with the actual output render; the normal visual channel has no qualified reference-image binding.'
    if domain=='excel':
        if any(term in text for term in ('formula','calculat','financial model','accounting','empty cell','audit','correct','dividend','count','average','dynamic','drop-down','helper column','data validation')):
            return 'uncovered','spreadsheet_scope_and_recalculation','Bind exact cells/ranges and authorized assumptions, then verify formulas/recalculated results; generic text or upstream target scores do not cover the entire task.'
        if any(term in text for term in ('preserv','format','layout','structure')):
            return 'uncovered','edit_preservation_scope','Freeze authorized edit scopes and preserved regions before enabling preservation; broad permission would hide regressions.'
        if any(term in text for term in ('chart','color','colour','marker','axis','legend','label','hierarch','doughnut','sunburst','waterfall')):
            return 'visual',None,None
        return 'uncovered','spreadsheet_requirement_review','A reviewer must resolve data/formula/appearance responsibilities and target locations.'
    if any(term in text for term in ('comment','header','footer','footnote','tracked change','redline','blank line','gray field','grey field','bold','boilerplate','structure','all other values unchanged')):
        return 'uncovered','word_package_and_preservation','Body-text extraction omits non-body parts and cannot prove formatting, annotations or unchanged regions; bind XML/structural scopes before admission.'
    return 'semantic',None,None


def draft_task(task):
    hashes={p:sha256_file(ordinary_file(p)) for p in task.input_files}
    checks=[Requirement(requirement_id='envelope-readable',description='Output opens in its Office parser.',
        check='file.readable',location=Location(artifact='output'),expected=True,critical=True,
        dimension='correctness',evidence_source='Declared task artifact domain'),
        Requirement(requirement_id='envelope-format',description='Output has the declared Office format.',
        check='file.format',location=Location(artifact='output'),expected=task.domain,critical=True,
        dimension='correctness',evidence_source='Declared task artifact domain')]
    if task.domain=='powerpoint' and 'one editable PowerPoint slide' in task.instruction:
        checks.append(Requirement(requirement_id='single-slide',description='The task explicitly requests one slide.',
            check='powerpoint.slide_count',location=Location(artifact='output'),expected=1,critical=True,
            dimension='correctness',evidence_source='Public task instruction'))
    if (task.domain=='powerpoint' and 'Use native editable text, shapes and connectors' in task.instruction
            and 'No external raster resources are authorized' in task.instruction):
        checks.append(Requirement(requirement_id='native-structure',description='Native objects with no slide/layout/master/chart image resources.',
            check='powerpoint.native_objects',location=Location(artifact='output'),
            expected={'min_text_shapes':1,'min_shapes':1,'min_connectors':1,'forbid_images':True},critical=True,
            dimension='correctness',evidence_source='Public task instruction',
            repair_hint='Use editable text, shapes and connectors. Keep visual reconstruction and source comparison requirements separate.'))
    inventory=[];obligations=[]
    for index,span in enumerate(instruction_spans(task.instruction),1):
        quote=span['source_quote'];rid=f'obligation-{index:03d}'
        method,gap,reason=route(task.domain,quote);ids=[]
        if method!='uncovered':
            cid=f'check-{index:03d}';ids=[cid]
            checks.append(Requirement(requirement_id=cid,description=quote,check='file.name' if method=='deterministic' else method,
                location=Location(artifact='output'),expected='output.pptx' if method=='deterministic' else {'obligation':quote,'full_task_instruction':task.instruction},
                options={'verify_sources':True,'required_content_channels':['body_text']} if method=='semantic' else {},
                critical=True,dimension='correctness',evidence_source='Exact public task instruction quote; input hashes frozen'))
        inventory.append(TaskRequirement(requirement_id=rid,source_quote=quote,source_ref='task.instruction',
            obligation=quote,validation_method=method,check_ids=ids))
        obligations.append({'requirement_id':rid,**span,'proposed_method':method,
            'check_ids':ids,'gap_kind':gap,'gap_reason':reason})
    inv=RequirementInventory(task_id=task.task_id,requirements=inventory,reviewed=False,
        provenance={'kind':'automated_draft','reviewer':None,'review_ref':None})
    spec=AcceptanceSpec(task_id=task.task_id,version='t31-requirement-draft-v1',artifacts={'output':task.domain},
        requirements=checks,dimension_weights={'correctness':1},input_hashes=hashes,
        task_context=task.model_dump(mode='json'),requirement_inventory=inv,evaluation_profile='task_acceptance',
        scope_note='Unreviewed requirement draft. Text/visual routes are proposals; envelope checks do not prove whole-task coverage. No reference answers included.')
    return {'task_id':task.task_id,'domain':task.domain,'task_hash':task_fingerprint(task),
        'input_hashes':hashes,'obligations':obligations,'spec':spec.model_dump(mode='json'),
        'admission':admission_for_spec(spec).model_dump(mode='json'),
        'capability_preflight':validate_acceptance_spec(spec,{}).model_dump(mode='json'),
        'required_assembly':['Bind authorized task/input source evidence to semantic channels.',
            'Verify rendering/page/reference coverage before visual checks.','Independent reviewer must bind task and acceptance-spec hashes.'],
        'live_ready':False}


def prepare(tasks_file,output):
    batches,families=read_tasks(tasks_file)
    owners={v:f for f in families for v in f.variant_ids}
    # Validate every original input before writing any draft output.
    for task in [t for rows in batches.values() for t in rows]:
        actual=canonical_json_hash(sorted(sha256_file(ordinary_file(p)) for p in task.input_files))
        if owners[task.task_id].variant_input_hashes.get(task.task_id)!=actual:
            raise ValueError('frozen family input hash differs: '+task.task_id)
    if Path(output).exists():raise FileExistsError(output)
    rows=[{**draft_task(task),'split':split,'family_id':owners[task.task_id].family_id}
          for split,tasks in batches.items() for task in tasks]
    output.mkdir(parents=True)
    for row in rows:
        name=canonical_json_hash(row['task_id'])[:20]+'.json';row['draft_file']=name
        (output/name).write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    counts=Counter(o['gap_kind'] for r in rows for o in r['obligations'] if o['gap_kind'])
    report={'schema_version':'t31-requirement-preparation-v1','source_bundle':str(tasks_file),
        'source_bundle_sha256':sha256_file(tasks_file),'task_count':len(rows),
        'domain_counts':dict(Counter(r['domain'] for r in rows)),
        'obligation_count':sum(len(r['obligations']) for r in rows),
        'proposed_check_routes':dict(Counter(o['proposed_method'] for r in rows for o in r['obligations'])),
        'gap_counts':dict(counts),'admission_counts':dict(Counter(r['admission']['status'] for r in rows)),
        'live_ready':False,'model_calls':0,'server_jobs':0,'reviewer_signatures_created':0,
        'coverage_scope':'Lossless instruction spans with proposed checks. Draft segmentation is not independent review or proof that every unit is atomic.',
        'tasks':[{'task_id':r['task_id'],'domain':r['domain'],'split':r['split'],'family_id':r['family_id'],
            'draft_file':r['draft_file'],'sha256':sha256_file(output/r['draft_file']),
            'mandatory_units':len(r['obligations']),'uncovered_units':sum(o['proposed_method']=='uncovered' for o in r['obligations'])} for r in rows]}
    (output/'preparation-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=prepare(args.tasks,args.output)
    print(json.dumps({k:v for k,v in report.items() if k!='tasks'}))
