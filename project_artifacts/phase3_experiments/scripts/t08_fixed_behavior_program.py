"""Trusted independent arithmetic task oracle; run only in Apptainer.

Model programs are frozen generation snapshots bound to exact skill hashes.
They run as children within the same no-network resource/cleanup boundary.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def main():
    from openpyxl import load_workbook
    taskfile=Path('inputs/tasks.json')
    taskset=json.loads(taskfile.read_text())
    packages={name:json.loads(Path('inputs',name+'.json').read_text()) for name in ('parent','candidate')}
    hashes={name:digest(package) for name,package in packages.items()}
    results={};details=[]
    for role,package_hash in hashes.items():
        program=taskset['programs'][package_hash]
        source=program['python_source']
        if hashlib.sha256(source.encode()).hexdigest()!=program['sha256']:raise ValueError('frozen program hash mismatch')
        results[role]={}
        for index,task in enumerate(taskset['tasks']):
            root=Path('scratch',role+'-'+str(index)).absolute()
            (root/'inputs').mkdir(parents=True)
            (root/'outputs').mkdir()
            (root/'inputs/values.json').write_text(json.dumps({'values':task['values']}))
            script=root/'program.py';script.write_text(source)
            run=subprocess.run([sys.executable,str(script)],cwd=root,capture_output=True,text=True,timeout=15)
            path=root/'outputs/answer.xlsx'
            value=None
            if run.returncode==0 and path.is_file():
                book=load_workbook(path,data_only=True)
                try:value=book['Summary']['B2'].value
                finally:book.close()
            passed=run.returncode==0 and type(value) in {int,float} and value==task['expected']
            results[role][task['task_id']]=passed
            details.append({'role':role,'task_id':task['task_id'],'exit_code':run.returncode,'actual':value,
                'expected':task['expected'],'passed':passed,'stdout':run.stdout[-4096:],'stderr':run.stderr[-4096:],
                'program_sha256':program['sha256'],'artifact_sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None})
    report={'parent_package_hash':hashes['parent'],'candidate_package_hash':hashes['candidate'],
        'taskset_hash':hashlib.sha256(taskfile.read_bytes()).hexdigest(),
        'rows':[{'task_id':t['task_id'],'parent_passed':results['parent'][t['task_id']],
                 'candidate_passed':results['candidate'][t['task_id']]} for t in taskset['tasks']],
        'details':details,'qualification_scope':'frozen actual model-generation snapshots; no live model inside no-network worker'}
    Path('outputs').mkdir(exist_ok=True)
    Path('outputs/behavior.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()
