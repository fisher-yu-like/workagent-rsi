"""Run a bounded non-COM pytest selection in the existing Apptainer image.

Linux-compatible wheels are prepared locally and imported only from a temporary
workspace. This runner never installs packages or changes the runtime image.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from workagent_rsi.apptainer_sandbox import ApptainerPolicy, ApptainerSSHExecutor
from workagent_rsi.hashing import sha256_file

SELECTION=[f'tests/test_{name}.py' for name in (
    'contracts','run_contracts','rsi_contracts','artifact_assessment_contracts','registry','promotion',
    'statistical_promotion','repeated_evaluation','memory_v2','human_label_provenance','review_audit',
    'llm_task_review','task_review_evidence','family_split_isolation',
    'experiment_budget_fairness','external_protocol_v2','release_claims')]

BOOTSTRAP=r'''
import contextlib,hashlib,importlib.metadata,io,json,os,platform,shutil,sys,tempfile,traceback,zipfile
from pathlib import Path,PurePosixPath
out=Path('/task/outputs');scratch=Path('/task/scratch')
work=Path(tempfile.mkdtemp(prefix='linux-check-',dir=scratch))
result={'actual_execution':False,'pytest_exit_code':None,'platform':sys.platform}
def extract(archive,target):
    with zipfile.ZipFile(archive) as bundle:
        entries=bundle.infolist()
        if sum(i.file_size for i in entries)>134217728:raise ValueError('expanded dependency/source budget exceeded')
        for item in entries:
            p=PurePosixPath(item.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in item.filename:raise ValueError('unsafe archive path')
        bundle.extractall(target)
try:
    policy=json.loads(Path('/task/inputs/test-policy.json').read_text())
    for name,digest in policy['archives'].items():
        path=Path('/task/inputs')/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('test archive changed')
    extract('/task/inputs/repository.zip',work/'repo')
    extract('/task/inputs/dependencies.zip',work/'deps')
    sys.path[:0]=[str(work/'deps'),str(work/'repo/src')]
    # Child CLI tests use the same temporary packages without a pip install.
    # The isolated bootstrap already has explicit sys.path entries; children
    # inherit only these two task-owned paths through PYTHONPATH.
    os.environ['PYTHONPATH']=os.pathsep.join([str(work/'deps'),str(work/'repo/src')])
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
    os.environ['PYTHONDONTWRITEBYTECODE']='1'
    os.environ['PYTEST_ADDOPTS']=''
    os.chdir(work/'repo')
    import pytest
    with (out/'pytest.stdout.txt').open('w') as stdout,(out/'pytest.stderr.txt').open('w') as stderr:
        with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            result['pytest_exit_code']=int(pytest.main(['-q','-p','no:cacheprovider','--basetemp='+str(work/'tmp'),
                '--junitxml='+str(out/'junit.xml'),*policy['tests']]))
    result.update(actual_execution=True,python=sys.version,implementation=platform.python_implementation(),
        selected_tests=policy['tests'],archives=policy['archives'],source_hashes=policy['source_hashes'],
        versions={n:importlib.metadata.version(n) for n in ['pytest','pydantic','pydantic_core','openpyxl','python-docx','python-pptx']})
except BaseException:
    result['error']=traceback.format_exc()
finally:
    os.chdir('/task')
    if work.resolve().parent!=scratch.resolve() or not work.name.startswith('linux-check-'):
        raise ValueError('refusing cleanup outside owned temporary workspace')
    shutil.rmtree(work)
    result['temporary_workspace_removed']=not work.exists()
    (out/'linux-result.json').write_text(json.dumps(result,indent=2)+'\n')
'''


def run(policy_file,wheels,output):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    workspace=output/'workspace';inputs=workspace/'inputs';inputs.mkdir(parents=True)
    paths={Path(p) for p in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode('utf-8').split('\0') if p}
    paths.update(p.relative_to(ROOT) for directory in ('src','tests') for p in (ROOT/directory).rglob('*.py') if '__pycache__' not in p.parts)
    paths={p for p in paths if (ROOT/p).is_file()}
    source_hashes={p.as_posix():sha256_file(ROOT/p) for p in sorted(paths) if p.parts[0] in {'src','tests'}}
    with zipfile.ZipFile(inputs/'repository.zip','x',compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(paths):bundle.write(ROOT/path,path.as_posix())
    with zipfile.ZipFile(inputs/'dependencies.zip','x',compression=zipfile.ZIP_DEFLATED) as bundle:
        names=set()
        for wheel in sorted(Path(wheels).glob('*.whl')):
            with zipfile.ZipFile(wheel) as package:
                for item in package.infolist():
                    if item.is_dir():continue
                    if item.filename in names:raise ValueError('wheel paths collide')
                    names.add(item.filename);bundle.writestr(item.filename,package.read(item))
    archives={p.name:sha256_file(p) for p in inputs.glob('*.zip')}
    if sum(p.stat().st_size for p in inputs.glob('*.zip'))>30000000:
        raise ValueError('test transfer exceeds conservative30MB budget')
    spec={'tests':SELECTION,'archives':archives,'source_hashes':source_hashes}
    (inputs/'test-policy.json').write_text(json.dumps(spec),encoding='utf-8')
    script=workspace/'linux-check.py';script.write_text(BOOTSTRAP,encoding='utf-8')
    policy=ApptainerPolicy.model_validate_json(Path(policy_file).read_text(encoding='utf-8'))
    executor=ApptainerSSHExecutor(policy)
    outcome=executor.run(script,workspace,timeout_seconds=240)
    actual=json.loads((workspace/'outputs/linux-result.json').read_text(encoding='utf-8')) if (workspace/'outputs/linux-result.json').exists() else {}
    traces=[json.loads((workspace/ref).read_text(encoding='utf-8')) for ref in outcome.trace_refs]
    guarded=bool(traces) and all(t.get('resource_observations',{}).get('passed') is True
                               and t.get('cleanup',{}).get('confirmed_absent') is True for t in traces)
    report={'exit_code':0 if outcome.status=='succeeded' and actual.get('pytest_exit_code')==0 and guarded else 1,
        'actual_execution':actual.get('actual_execution',False),'platform':actual.get('platform'),
        'pytest':actual,'sandbox_outcome':outcome.model_dump(mode='json'),
        'resource_and_cleanup_verified':guarded,'model_calls':0,'server_installs':0,
        'transfer_bytes':sum(p.stat().st_size for p in inputs.glob('*.zip')),
        'source_archive_expanded_bytes':sum((ROOT/p).stat().st_size for p in paths),
        'wheel_expanded_bytes':sum(i.file_size for wheel in Path(wheels).glob('*.whl') for i in zipfile.ZipFile(wheel).infolist())}
    (output/'linux-non-com.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sandbox-policy',type=Path,required=True)
    parser.add_argument('--wheels',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=run(args.sandbox_policy,args.wheels,args.output)
    print(json.dumps({k:v for k,v in result.items() if k not in {'pytest','sandbox_outcome'}}))
    return result['exit_code']

if __name__=='__main__':raise SystemExit(main())
