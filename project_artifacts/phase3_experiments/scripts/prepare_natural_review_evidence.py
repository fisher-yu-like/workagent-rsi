"""Freeze mixed-format text partitions for natural outputs; no judge calls."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from workagent_rsi.hashing import sha256_file
from workagent_rsi.review_evidence import prepare_file_evidence
from workagent_rsi.view_safety import ordinary_file, relative_reference


def prepare(public,output):
    manifest_path=ordinary_file(public/'review-manifest.json')
    manifest_hash=sha256_file(manifest_path)
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    cases=[r for r in manifest['cases'] if r['cohort']=='natural-blind']
    if len(cases)!=20 or len({r['case_id'] for r in cases})!=20:
        raise ValueError('expected twenty distinct natural cases')
    if output.exists():raise FileExistsError('new evidence output required')
    output.mkdir(parents=True)
    rows=[]
    for case in cases:
        artifact=ordinary_file(public/relative_reference(case['artifact']))
        if sha256_file(artifact)!=case['artifact_hash']:raise ValueError('natural artifact changed')
        files=[]
        for n,name in enumerate([case['artifact'],*case['inputs']]):
            path=ordinary_file(public/relative_reference(name))
            before=sha256_file(path)
            try:
                evidence=prepare_file_evidence(path,'output' if n==0 else f'input-{n}')
                filename=f'{case["case_id"]}-{n}.json'
                (output/filename).write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                row={'file':name,'source_sha256':before,'evidence':filename,
                     'evidence_sha256':sha256_file(output/filename),
                     'partitions':len(evidence['partition']['partitions']),
                     'text_partition_complete':evidence['text_partition_complete'],
                     'parser_warnings':evidence['parser_warnings'],
                     'status':'available' if evidence['text_partition_complete'] else 'gap'}
            except (ValueError,TypeError,KeyError,IndexError,NotImplementedError) as exc:
                row={'file':name,'source_sha256':before,'status':'gap','reason':type(exc).__name__+': '+str(exc)}
            if sha256_file(path)!=before:raise ValueError('source changed during natural preparation')
            files.append(row)
        rows.append({'case_id':case['case_id'],'files':files})
    if sha256_file(manifest_path)!=manifest_hash:raise ValueError('review manifest changed')
    report={'schema_version':'natural20-text-partitions-v1','manifest_sha256':manifest_hash,
            'cases':rows,'case_count':len(rows),'gap_files':sum(f['status']=='gap' for r in rows for f in r['files']),
            'warning_files':sum(bool(f.get('parser_warnings')) for r in rows for f in r['files']),
            'text_partitions':sum(f.get('partitions',0) for r in rows for f in r['files']),
            'model_calls':0,'server_jobs':0,'human_labels_read':False,'reference_answers_read':False,
            'live_ready':False,'whole_task_coverage_qualified':False,
            'remaining':['Bind text/source partitions into review requests and cross-partition checks.',
                         'Resolve two actual render gaps and qualify native object/formula coverage.',
                         'Freeze a new complete model request budget before requesting approval.']}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=prepare(args.public,args.output)
    print(json.dumps({k:v for k,v in report.items() if k!='cases'}))
