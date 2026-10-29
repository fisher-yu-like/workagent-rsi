"""Actual candidate-container denial of an owned evaluator-side canary.

No final-test content, model call, installation or global server change. The
same SSH account remains the host owner; this does not prove separate principals.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import shlex
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from workagent_rsi.apptainer_sandbox import ApptainerPolicy,ApptainerSSHExecutor
from workagent_rsi.environment_manifest import capture_environment
from workagent_rsi.hashing import sha256_file


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    capture_environment(ROOT,args.output/'environment.json')
    policy=ApptainerPolicy.model_validate_json(args.policy.read_text(encoding='utf-8'))
    start=datetime.now(timezone.utc).isoformat();remote='/tmp/wrsi-final-boundary-'+uuid4().hex
    logs=[]
    def ssh(code):
        command=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',policy.ssh_host,'/usr/bin/python3 -c '+shlex.quote(code)]
        result=subprocess.run(command,capture_output=True,text=True,timeout=45)
        logs.append({'command':command,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        if result.returncode: raise OSError('evaluator-side SSH preparation failed')
        return json.loads(result.stdout)
    outcome=None;facts={};cleanup=False;error=None
    try:
        host=ssh(f'''import os,json,secrets,shutil,subprocess
from pathlib import Path
p=Path({remote!r});p.mkdir(mode=0o700);(p/'canary').write_bytes(secrets.token_bytes(32));(p/'canary').chmod(0o600)
q=subprocess.run(['du','-sk',{policy.remote_image!r}],capture_output=True,text=True,timeout=30)
print(json.dumps({{'uid':os.getuid(),'gid':os.getgid(),'canary_bytes':32,'private_mode':oct(p.stat().st_mode & 0o777),'runtime_du':q.stdout.strip(),'runtime_du_exit':q.returncode,'free_tmp_bytes':shutil.disk_usage('/tmp').free}}))''')
        workspace=args.output/'candidate-task';(workspace/'inputs').mkdir(parents=True)
        (workspace/'inputs/public.txt').write_text('public-input')
        script=workspace/'check_boundary.py'
        script.write_text(f'''import json
from pathlib import Path
p=Path({remote!r})/'canary'
try:
    p.read_bytes();denied=False
except OSError: denied=True
try:
    Path('inputs/public.txt').write_text('changed');readonly=False
except OSError: readonly=True
Path('outputs/facts.json').write_text(json.dumps({{'private_unreadable':denied,'input_readonly':readonly,'public_input_readable':Path('inputs/public.txt').read_text()=='public-input'}}))
''')
        outcome=ApptainerSSHExecutor(policy).run(script,workspace,60)
        if outcome.status=='succeeded': facts=json.loads((workspace/'outputs/facts.json').read_text())
    except Exception as exc:
        error=f'{type(exc).__name__}: {exc}'
    finally:
        try:
            cleanup=ssh(f'''import os,json
from pathlib import Path
p=Path({remote!r})
assert p.parent==Path('/tmp') and p.name.startswith('wrsi-final-boundary-')
if p.exists():
    assert p.stat().st_uid==os.getuid() and not p.is_symlink()
    (p/'canary').unlink(missing_ok=True);p.rmdir()
print(json.dumps({{'removed':not p.exists()}}))''')['removed']
        except Exception as exc: error=f'cleanup unconfirmed: {type(exc).__name__}'
    qualified=bool(facts) and all(facts.values()) and cleanup and outcome is not None and outcome.status=='succeeded'
    report={'status':'passed' if qualified else 'blocked','candidate_mount_boundary_qualified':qualified,
        'separate_service_principal':False,'formal_final_corpus_present':False,'host_owner_isolation_claim':False,
        'facts':facts,'owned_canary_cleanup':cleanup,'error':error,'model_calls':0,
        'remote_added_persistent_bytes':0 if cleanup else None,
        'host_resources':host if 'host' in locals() else None,
        'outcome':outcome.model_dump(mode='json') if outcome else None}
    (args.output/'boundary-report.json').write_text(json.dumps(report,indent=2)+'\n')
    (args.output/'transport-log.json').write_text(json.dumps(logs,indent=2)+'\n')
    record={'command':[sys.executable,*sys.argv],'cwd':str(ROOT),'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'started_at':start,'ended_at':datetime.now(timezone.utc).isoformat(),'exit_code':0 if qualified else 1,
        'source_hash':sha256_file(Path(__file__)),'files':{p.relative_to(args.output).as_posix():sha256_file(p) for p in args.output.rglob('*') if p.is_file()}}
    (args.output/'run.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(report));return record['exit_code']


if __name__=='__main__': raise SystemExit(main())
