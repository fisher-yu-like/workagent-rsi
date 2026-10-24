"""Read-only, bounded hypotheses from authorized develop execution evidence.

No files are opened or scripts executed here. Trace owners supply exact text,
hashes and visibility. Output mismatch alone never establishes a cause.
"""
import ast
import hashlib
import json
import re

from .hashing import canonical_json_hash
from .rsi_contracts import FailureDiagnosis,DiagnosisEvidence
from .run_contracts import ExecutionOutcome


def _authorized(trace):
    items=[]
    evidence=trace.get('evidence',[])
    if not isinstance(evidence,list):return items
    for row in evidence[:16]:
        if not isinstance(row,dict) or row.get('authorized') is not True or row.get('split')!='develop' or row.get('feedback_visibility')!='develop':continue
        text=row.get('text')
        if row.get('kind') not in {'script','stderr','input_manifest','file_events'} or not isinstance(text,str) or len(text)>100000:continue
        digest=hashlib.sha256(text.encode('utf-8')).hexdigest()
        if row.get('sha256')!=digest:continue
        items.append({**row,'ref':row['kind']+':'+digest,'sha256':digest})
    return items


def _quote(row,text=None,line=None):
    quote=row['text'] if text is None else text
    if not quote or quote not in row['text'] or len(quote)>4000:return None
    return DiagnosisEvidence(ref=row['ref']+(f'#L{line}' if line else ''),kind=row['kind'],quote=quote,
        source_sha256=row['sha256'],line_start=line,line_end=line)


def diagnose_failure(issue,execution:ExecutionOutcome,trace:dict)->list[FailureDiagnosis]:
    execution=ExecutionOutcome.model_validate(execution.model_dump())
    if trace.get('split')!='develop' or trace.get('hidden_test') or (issue is not None and issue.feedback_visibility!='develop'):return []
    if execution.status in {'succeeded','not_run'} and issue is None:return []
    items=_authorized(trace)
    run_id=str(trace.get('run_id','unknown'))
    if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,128}',run_id):run_id='run-'+canonical_json_hash(run_id)[:16]
    origin=execution.failure_origin
    private=origin in {'environment','model_transport','user_input'}
    def make(hypothesis,action,falsify,details=(),failure_class='planning',component='office_script',strength=0):
        details=[d for d in details if d is not None]
        refs=list(dict.fromkeys(d.ref for d in details)) or ['execution:'+canonical_json_hash(execution.model_dump(mode='json'))]
        if issue is not None:refs.append('issue:'+canonical_json_hash(issue.model_dump(mode='json')))
        payload={'run':run_id,'hypothesis':hypothesis,'refs':refs}
        return [FailureDiagnosis(diagnosis_id=canonical_json_hash(payload)[:20],run_ids=[run_id],failure_class=failure_class,
            evidence_refs=refs,causal_hypothesis=hypothesis,recommended_component=component,confidence=strength,
            confidence_basis='uncalibrated_evidence_rule_strength; not a probability',recommended_action=action,
            falsification_check=falsify,evidence_details=details,feedback_visibility='evaluation_only' if private else 'develop')]
    if private:
        return make('Execution environment or transport failed; artifact cause remains unknown.',
            'Restore the recorded capability before another real attempt.','Reprobe the same frozen environment and transport.',
            failure_class='evaluator',component='tool_policy')
    scripts=[i for i in items if i['kind']=='script']
    logs=[i for i in items if i['kind']=='stderr']
    if execution.status in {'failed','timeout'} and origin=='agent_execution':
        for log in logs:
            errors=list(re.finditer(r'(?m)^(SyntaxError|AttributeError|KeyError):[^\n]*',log['text']))
            if not errors:continue
            error=errors[-1];kind=error.group(1)
            frames=re.findall(r'File "([^"]+)", line (\d+)',log['text'])
            for script in scripts:
                name=script.get('name')
                if not isinstance(name,str) or '/' in name or '\\' in name:continue
                positions=[int(line) for file,line in frames if re.split(r'[/\\]',file)[-1]==name]
                lines=script['text'].splitlines()
                if not positions or not 1<=positions[-1]<=len(lines):continue
                line=positions[-1];code=lines[line-1]
                details=[_quote(script,code,line),_quote(log,error.group(0))]
                if any(d is None for d in details):continue
                hypothesis=f'{kind} was reported at {name} line {line}: {error.group(0)}'
                actions={'SyntaxError':'Correct the cited syntax before running the same task.',
                    'AttributeError':'Check the cited API against the installed library and replace the unsupported access.',
                    'KeyError':'Check the requested worksheet/key against the authorized current input before accessing it.'}
                return make(hypothesis,actions[kind],'Rerun the same input and verify the cited exception disappears; then reassess the artifact.',
                    details,failure_class='input' if kind=='KeyError' else 'tool',strength=.9)
    if issue is not None and issue.kind=='artifact_defect' and execution.status=='succeeded':
        for script in scripts:
            try:tree=ast.parse(script['text'])
            except (SyntaxError,ValueError):continue
            lines=script['text'].splitlines()
            sheets={n.targets[0].id:n.value.slice.value for n in ast.walk(tree) if isinstance(n,ast.Assign)
                and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and isinstance(n.value,ast.Subscript)
                and isinstance(n.value.slice,ast.Constant) and isinstance(n.value.slice.value,str)}
            for data in [i for i in items if i['kind']=='input_manifest']:
                try:counts=json.loads(data['text'])
                except ValueError:continue
                if not isinstance(counts,dict) or set(counts)!={'sheet','first_data_row','last_data_row','row_count','max_row'}:continue
                if counts['sheet']!=issue.location.sheet:continue
                if any(type(counts[k]) is not int or counts[k]<1 for k in ('first_data_row','last_data_row','row_count','max_row')):continue
                if counts['last_data_row']!=counts['first_data_row']+counts['row_count']-1 or counts['max_row']!=counts['last_data_row']:continue
                for node in ast.walk(tree):
                    if not isinstance(node,ast.For) or not isinstance(node.iter,ast.Call):continue
                    call=node.iter
                    if not isinstance(call.func,ast.Name) or call.func.id!='range' or len(call.args)!=2 or call.keywords:continue
                    start,end=call.args
                    if not (isinstance(start,ast.Constant) and type(start.value) is int and start.value==counts['first_data_row']
                        and isinstance(end,ast.Attribute) and end.attr=='max_row' and isinstance(end.value,ast.Name)
                        and sheets.get(end.value.id)==counts['sheet']):continue
                    if not any(isinstance(n,ast.AugAssign) and isinstance(n.op,ast.Add) for n in ast.walk(node)):continue
                    details=[_quote(script,lines[node.lineno-1],node.lineno),_quote(data)]
                    if any(d is None for d in details):continue
                    return make(f'The aggregation range excludes its max_row endpoint; the authorized input has {counts["row_count"]} data rows ending at row {counts["last_data_row"]}. The last input row may be omitted.',
                        'Check the loop endpoint against the current input count and include the final data row.',
                        'Recompute a fixture with a nonzero last row and an appended last row; this hypothesis is falsified if both match the independent input oracle.',
                        details,failure_class='semantic',strength=.75)
            for data in [i for i in items if i['kind']=='file_events']:
                try:events=json.loads(data['text'])
                except ValueError:continue
                if not isinstance(events,list):continue
                writes={}
                for event in events[:128]:
                    if not isinstance(event,dict):continue
                    path=event.get('path');digest=event.get('sha256');sequence=event.get('sequence')
                    if (event.get('operation')!='write' or not isinstance(path,str) or not path.startswith('outputs/') or '\\' in path or '..' in path.split('/')
                        or not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest) or type(sequence) is not int or sequence<1):continue
                    writes.setdefault(path,[]).append((sequence,digest))
                for path,versions in writes.items():
                    if path not in execution.artifact_refs:continue
                    if len({s for s,h in versions})<2 or len({h for s,h in versions})<2:continue
                    saves=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
                        and n.func.attr=='save' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value==path]
                    if len(saves)<2:continue
                    details=[_quote(script,lines[saves[-1].lineno-1],saves[-1].lineno),_quote(data)]
                    if any(d is None for d in details):continue
                    return make(f'Distinct writes target {path}; the later save may overwrite the intended artifact.',
                        'Inspect the final writer and ensure the intended workbook is the final saved artifact.',
                        'Compare the artifact after each recorded write against the requirement; a correct final artifact falsifies this overwrite hypothesis.',
                        details,failure_class='semantic',strength=.7)
    return make('Cause unknown: the observed failure or output mismatch alone does not establish a causal explanation.',
        'Collect authorized script, stderr and relevant input/write evidence before choosing a causal repair.',
        'Reproduce with the same input and inspect the cited execution record; reject any hypothesis unsupported by that trace.')
