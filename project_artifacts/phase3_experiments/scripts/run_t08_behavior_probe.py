"""Generate frozen model programs, then verify their actual isolated behavior.

The public fixed taskset and numeric oracles precede model generation. Models
receive a generic task and skill only, never the oracle cases. This qualifies
the candidate-verifier boundary on authored tasks, not general skill quality.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO=next(p for p in Path(__file__).resolve().parents if (p/'pyproject.toml').is_file())
sys.path.insert(0,str(REPO/'src'))
from workagent_rsi.apptainer_sandbox import ApptainerPolicy,ApptainerSSHExecutor
from workagent_rsi.behavior_probe import FixedSandboxBehaviorProbe
from workagent_rsi.environment_manifest import capture_environment
from workagent_rsi.hashing import canonical_json_hash,sha256_file
from workagent_rsi.rsi_contracts import CandidatePatch,AtomicEdit
from workagent_rsi.verifier import CandidateVerifier,VerificationPolicy
from workagent_rsi.workagent_provider import WorkAgentSkill
from qualification_cli import QualificationCLI


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def generate(package,root,runner):
    root.mkdir()
    schema={'type':'object','properties':{'python_source':{'type':'string'}},'required':['python_source'],'additionalProperties':False}
    write(root/'schema.json',schema)
    output=(root/'output.json').resolve()
    prompt=('Write one self-contained Python program as JSON python_source. No tools or execution. '
        'The runtime has Python and openpyxl. Read inputs/values.json, an object containing values (a list of numbers or null). '
        'Write a real outputs/answer.xlsx, sheet Summary, numeric sum in B2. Follow this skill exactly. '
        'No hardcoded answers or branching on task names. Skill: '+json.dumps(package))
    (root/'prompt.txt').write_text(prompt,encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='wrsi-generation-') as folder:
        command=[shutil.which('codex'),'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check',
            '--sandbox','read-only','--model','gpt-6.1-sol','--json','--color','never',
            '--output-schema',str((root/'schema.json').resolve()),'--output-last-message',str(output),'-C',folder,
            '-c','approval_policy="never"','-c','web_search="disabled"','-c','model_reasoning_effort="low"',
            '-c','project_doc_max_bytes=0']
        for feature in ('shell_tool','multi_agent','apps','plugins','hooks','browser_use','computer_use','image_generation','view_image','skill_search'):
            command.extend(['-c',f'features.{feature}=false'])
        command.extend(['-c','features.skip_host_skill_discovery=true','-'])
        result=runner(command,Path(folder),90,prompt)
    (root/'stdout.jsonl').write_text(result.stdout or '',encoding='utf-8')
    (root/'stderr.txt').write_text(result.stderr or '',encoding='utf-8')
    write(root/'process.json',{'exit_code':result.returncode,'package_hash':canonical_json_hash(package)})
    if result.returncode or not output.exists():raise ValueError('model generation unavailable; no automatic retry')
    code=json.loads(output.read_text(encoding='utf-8'))['python_source']
    if not isinstance(code,str) or not code.strip():raise ValueError('model produced no program')
    import hashlib
    return {'python_source':code,'sha256':hashlib.sha256(code.encode()).hexdigest(),
        'package_hash':canonical_json_hash(package),'generation_record':root.name}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy',type=Path,required=True)
    parser.add_argument('--live-policy',type=Path,required=True)
    options=parser.parse_args()
    runner=QualificationCLI(options.live_policy)
    root=REPO/'project_artifacts/results/hardening-v2/T08-real'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    root.mkdir(parents=True)
    capture_environment(REPO,root/'environment.json')
    record={'started_at':datetime.now(timezone.utc).isoformat(),'command':[sys.executable,*sys.argv],
        'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'scope':'authored tasks, frozen actual model-generation snapshots, real isolated behavior',
        'source_hashes':{p.name:sha256_file(p) for p in [Path(__file__),Path(__file__).with_name('t08_fixed_behavior_program.py'),
            Path(__file__).with_name('qualification_cli.py'),REPO/'src/workagent_rsi/behavior_probe.py',REPO/'src/workagent_rsi/verifier.py']}}
    policy=ApptainerPolicy.model_validate_json(options.policy.read_text(encoding='utf-8'))
    write(root/'sandbox-policy.json',policy.model_dump(mode='json'))
    parent=WorkAgentSkill(instructions='Sum all numeric entries in the current values list; ignore nulls.').model_dump(mode='json')
    packages={'parent':parent,
        'good':{**parent,'instructions':parent['instructions']+' Make the Summary header bold and verify the output path.'},
        'bad':{**parent,'instructions':'Sum only the first two numeric entries in the current values list; ignore all remaining entries.'}}
    tasks=[{'task_id':'base','protected':False,'values':[10,15],'expected':25},
        {'task_id':'last-row','protected':True,'values':[10,15,7],'expected':32},
        {'task_id':'negative-null-zero','protected':True,'values':[-10,None,0,15,7],'expected':12}]
    write(root/'fixed-tasks-before-generation.json',{'tasks':tasks})
    write(root/'packages.json',packages)
    reports={}
    try:
        programs={canonical_json_hash(package):generate(package,root/('generation-'+name),runner) for name,package in packages.items()}
        taskset=root/'fixed-taskset.json'
        write(taskset,{'tasks':tasks,'programs':programs})
        source=Path(__file__).with_name('t08_fixed_behavior_program.py')
        shutil.copyfile(source,root/source.name)
        probe=FixedSandboxBehaviorProbe(executor=ApptainerSSHExecutor(policy),program=source,program_sha256=sha256_file(source),
            taskset=taskset,taskset_sha256=sha256_file(taskset),output_root=root/'behavior',qualification='isolated_run')
        workspace=root/'candidate-workspace';workspace.mkdir()
        write(workspace/'skill.json',parent)
        verifier=CandidateVerifier(behavior_probe=probe)
        for name in ('good','bad'):
            patch=CandidatePatch(candidate_id=name,parent_version='1.0.0',provider='authored-control',provider_version='1',
                diagnosis_refs=[canonical_json_hash(tasks)],edit_budget=1,created_at=datetime.now(timezone.utc),
                atomic_edits=[AtomicEdit(component='prompt',target_path='skill.json',patch=json.dumps({'instructions':packages[name]['instructions']}),
                    hypothesis='Preserve complete current-input summation',expected_metric='fixed task acceptance')])
            report=verifier.verify(patch,workspace,VerificationPolicy(allowed_targets={'skill.json'},timeout_seconds=90),
                skill_model=WorkAgentSkill,parent_package=parent,parent_version='1.0.0',edit_budget=1)
            reports[name]=report.model_dump(mode='json')
            write(root/'candidate-verifier/report-examples.json',reports)
        passed=reports['good']['passed'] and not reports['bad']['passed'] and reports['bad']['behavior_status']=='failed'
        passed=passed and reports['bad']['test_results']['behavior_probe']['protected_regressions']>0
        passed=passed and json.loads((workspace/'skill.json').read_text())==parent
        record.update(status='passed' if passed else 'failed',parent_unchanged=json.loads((workspace/'skill.json').read_text())==parent,
            taskset_sha256=sha256_file(taskset),program_sha256=sha256_file(source),reports=reports)
    except Exception as exc:
        record.update(status='blocked',error_type=type(exc).__name__,error=str(exc))
    record.update(ended_at=datetime.now(timezone.utc).isoformat(),exit_code=0 if record['status']=='passed' else 1)
    write(root/'run.json',record)
    print(json.dumps({'evidence':str(root.relative_to(REPO)),'status':record['status'],'error':record.get('error')}))
    return record['exit_code']


if __name__=='__main__':sys.exit(main())
