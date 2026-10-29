"""Bounded read evidence and separate agent-declared plans for the current task."""
from pathlib import Path
import json
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel,ConfigDict,Field,model_validator

from .hashing import sha256_file
from .view_safety import ordinary_file,checked_path,relative_reference
from .repair_loop import write_record


class TaskObservation(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
    input_hashes: dict[str,str]
    inspected_structure: dict
    requested_changes: list[str]
    chosen_operations: list[str]
    verification_plan: list[str]
    status: Literal['observed','partial','not_observed']='not_observed'
    inspection_evidence: list[dict]=Field(default_factory=list,max_length=32)
    plan_origin: Literal['agent_declared']='agent_declared'
    execution_mode: Literal['create','edit']

    @model_validator(mode='after')
    def evidence_bound(self):
        if any(len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest) for digest in self.input_hashes.values()):
            raise ValueError('observations require exact SHA-256 input identities')
        if len(json.dumps(self.model_dump(mode='json'),ensure_ascii=False).encode('utf-8'))>1_000_000:
            raise ValueError('task observation exceeds evidence bound')
        if not set(self.inspected_structure)<=set(self.input_hashes):
            raise ValueError('inspection does not belong to current inputs')
        if self.status=='observed' and set(self.inspected_structure)!=set(self.input_hashes):
            raise ValueError('observed status requires every authorized input')
        return self


def inspection_program(config):
    source=Path(__file__).with_name('office_input_inspector.py').read_text(encoding='utf-8')
    return source+'\nrun_inspection(json.loads('+repr(json.dumps(config))+'))\n'


def inspect_input_tool(arguments,workspace,*,timeout_seconds,sandbox,records):
    """Inspect one named staged input in the same T04 sandbox. Never a host fallback."""
    from .workagent_provider import _native_tool_path,_execute_native_tool
    if records is None:raise ValueError('inspection requires host-owned records')
    workspace=checked_path(workspace);records=checked_path(records)
    value=arguments.get('path');source=_native_tool_path(workspace,value)
    manifest=json.loads(ordinary_file(workspace/'input_manifest.json').read_text(encoding='utf-8'))
    entry=next((i for i in manifest['files'] if i['copied']==value),None)
    if entry is None or not str(value).startswith('inputs/') or sha256_file(ordinary_file(source))!=entry['copy_sha256']:
        raise ValueError('inspect_office accepts only the exact authorized input snapshot')
    domain={'.xlsx':'excel','.docx':'word','.pptx':'powerpoint'}.get(source.suffix)
    if domain is None:raise ValueError('unsupported Office input')
    identifier=uuid4().hex
    config={'input':value,'domain':domain,'output':'outputs/inspection-'+identifier+'.json'}
    script=workspace/('inspection-'+identifier+'.py')
    script.write_text(inspection_program(config),encoding='utf-8',newline='\n')
    # Authored qualification executors can register this exact trusted program;
    # production sandbox executors expose no registration or host execution path.
    if hasattr(sandbox,'register_inspection'):sandbox.register_inspection(script,config)
    result=_execute_native_tool.__wrapped__('run_python',{'path':script.name},workspace,
        timeout_seconds=timeout_seconds,sandbox=sandbox,records=records)
    if not result['ok']:return result
    output=ordinary_file(workspace/config['output'])
    if output.stat().st_size>1_000_000:raise ValueError('inspection evidence exceeds bound')
    report=json.loads(output.read_text(encoding='utf-8'))
    if (report.get('input_path')!=value or report.get('input_sha256')!=entry['copy_sha256']
            or sha256_file(source)!=entry['copy_sha256']):raise ValueError('inspection input/hash mismatch')
    report.update(schema_version='office-inspection-v1',execution=result['execution'],
                  script_sha256=result['script_sha256'],program_sha256=sha256_file(Path(__file__).with_name('office_input_inspector.py')))
    ref='input-inspections/'+identifier+'.inspection.json'
    write_record(records/ref,report)
    return {**result,'inspection':report,'inspection_ref':ref,'inspection_sha256':sha256_file(records/ref)}


def capture_task_observation(task,workspace,records,manifest):
    from .workagent_office import _task_mode
    hashes={i['copied']:i['copy_sha256'] for i in manifest['files']}
    structures={};evidence=[];operations=[];verification=[]
    log=Path(records)/'tool_events.jsonl'
    if log.exists():
        log=ordinary_file(log)
        if log.stat().st_size>5_000_000:raise ValueError('tool observation log exceeds bound')
        for line in log.read_text(encoding='utf-8').splitlines()[-256:]:
            event=json.loads(line)
            if event.get('name')!='inspect_office' or event.get('result',{}).get('ok') is not True:continue
            result=event['result'];ref=relative_reference(result['inspection_ref'])
            path=ordinary_file(Path(records).joinpath(*ref.parts))
            if not path.resolve().is_relative_to(Path(records).resolve()) or sha256_file(path)!=result['inspection_sha256']:
                raise ValueError('inspection record changed or escaped the records directory')
            report=json.loads(path.read_text(encoding='utf-8'));name=report['input_path']
            if (hashes.get(name)!=report['input_sha256'] or report['execution']['status']!='succeeded'
                    or report['program_sha256']!=sha256_file(Path(__file__).with_name('office_input_inspector.py'))):
                raise ValueError('inspection evidence does not bind to this task/runtime')
            structures[name]=report['structure'];evidence.append({'ref':str(ref),'sha256':result['inspection_sha256'],
                'input_path':name,'script_sha256':report['script_sha256']})
            args=event.get('arguments',{})
            for key,target in [('chosen_operations',operations),('verification_plan',verification)]:
                values=args.get(key,[])
                if isinstance(values,list):target.extend(v[:2000] for v in values[:16] if isinstance(v,str))
    status='observed' if set(structures)==set(hashes) and all(s.get('complete') is True for s in structures.values()) else 'partial' if structures else 'not_observed'
    observation=TaskObservation(input_hashes=hashes,inspected_structure=structures,
        requested_changes=[task.instruction],chosen_operations=operations,verification_plan=verification,
        status=status,inspection_evidence=evidence,execution_mode=_task_mode(task))
    write_record(Path(records)/'task-observation.json',observation.model_dump(mode='json'))
    return observation
