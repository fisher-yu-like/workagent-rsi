"""Human submissions require external receipts; model labels never count."""
from __future__ import annotations

from datetime import datetime
from datetime import timezone
import json
from pathlib import Path
from typing import Literal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .calibration_metrics import proportion
from .hashing import canonical_json_hash,sha256_file
from .view_safety import ordinary_file


class HumanLabel(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    case_id: str=Field(min_length=1)
    reviewer_id: str=Field(min_length=1)
    label: Literal['PASS','FAIL','PARTIAL','INCOMPLETE']
    defect_locations: list[str]
    timestamp: datetime
    evidence_ref: str=Field(min_length=1)
    rubric_hash: str=Field(pattern=r'^[0-9a-f]{64}$')
    source_kind: Literal['human']
    submission_hash: str=Field(pattern=r'^[0-9a-f]{64}$')

    @field_validator('reviewer_id')
    @classmethod
    def actual_reviewer(cls,value):
        if re.search(r'codex|chatgpt|claude|openai|assistant|gpt-|model|agent',value,re.I):
            raise ValueError('model identity cannot be a human reviewer')
        return value

    @field_validator('timestamp')
    @classmethod
    def aware_time(cls,value):
        if value.utcoffset() is None: raise ValueError('human timestamp needs a timezone')
        return value


def evaluator_identity_for_rubric(base_identity: str,rubric: dict) -> str:
    return canonical_json_hash({'base_evaluator':base_identity,'rubric':rubric})


def intake_human_submission(submission: Path, output: Path, *, reviewer_id: str, evidence_ref: str,
                            review_manifest: dict, judge_revealed: bool=False) -> dict:
    """Controller entrypoint after an actual reviewer supplies a file.

    The caller must have observed the external submission. This function does
    not infer human provenance from a file's self-declared source_kind.
    """
    if judge_revealed: raise ValueError('labels must be frozen before judge results are revealed')
    if not evidence_ref.strip(): raise ValueError('external submission reference required')
    submission=ordinary_file(submission)
    if submission.stat().st_size>1048576: raise ValueError('human submission exceeds1MB')
    raw=submission.read_bytes();digest=sha256_file(submission)
    payload=json.loads(raw)
    if not isinstance(payload,dict) or payload.get('model_identity') or payload.get('source_kind') not in {None,'human'}:
        raise ValueError('model/unknown submission source cannot be human')
    if payload.get('rubric_hash')!=review_manifest['rubric_hash']: raise ValueError('submission rubric mismatch')
    now=datetime.now(timezone.utc).isoformat();labels=[]
    required=set(review_manifest['case_ids'])
    for row in payload['labels']:
        if row.get('model_identity') or row.get('source_kind') not in {None,'human'}:
            raise ValueError('model labels cannot be counted as human')
        if row.get('reviewer_id',reviewer_id)!=reviewer_id: raise ValueError('reviewer binding mismatch')
        labels.append(HumanLabel(case_id=row['case_id'],reviewer_id=reviewer_id,label=row['label'],
            defect_locations=row.get('defect_locations',[]),timestamp=row.get('timestamp',now),
            evidence_ref=evidence_ref,rubric_hash=payload['rubric_hash'],source_kind='human',submission_hash=digest))
    ids=[l.case_id for l in labels]
    if len(set(ids))!=len(ids) or not set(ids)<=required: raise ValueError('duplicate or unknown human case')
    receipt={'source_kind':'reviewer_file','submission_hash':digest,'reviewer_id':reviewer_id,
        'evidence_ref':evidence_ref,'case_ids':ids,'rubric_hash':payload['rubric_hash'],'received_at':now,'judge_revealed':False}
    output=Path(output)
    if output.exists(): raise FileExistsError(output)
    output.mkdir(parents=True)
    (output/'external-submission.json').write_bytes(raw)
    with (output/'human-labels.jsonl').open('x',encoding='utf-8') as stream:
        for label in labels: stream.write(label.model_dump_json()+'\n')
    (output/'submission-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return receipt


def compare_human_labels(labels, decisions, *, review_manifest: dict, submission_receipts=()) -> dict:
    """Receipts come from user-message/file intake, never from a model signature.

    This verifies recorded provenance bindings, not the identity of a human in
    an unauthenticated JSON file. The controller must preserve the original
    external submission and create receipts from that actual intake.
    """
    required=set(review_manifest['case_ids'])
    rubric=review_manifest['rubric_hash']
    parsed=[HumanLabel.model_validate(l) for l in labels]
    if len({l.case_id for l in parsed})!=len(parsed): raise ValueError('duplicate human label case')
    if len({d['case_id'] for d in decisions})!=len(decisions): raise ValueError('duplicate judge decision')
    receipts={}
    for receipt in submission_receipts:
        if receipt.get('source_kind') not in {'user_message','reviewer_file'}: continue
        if receipt.get('judge_revealed') is not False: raise ValueError('blind review was already revealed')
        if receipt.get('rubric_hash')!=rubric: raise ValueError('receipt rubric changed')
        if not receipt.get('received_at'): raise ValueError('submission receipt timestamp required')
        receipts[(receipt.get('submission_hash'),receipt.get('reviewer_id'),receipt.get('evidence_ref'))]=receipt
    accepted=[]
    for label in parsed:
        if label.case_id not in required: raise ValueError('human case not in frozen blind pack')
        if label.rubric_hash!=rubric: raise ValueError('human rubric changed; new evaluator identity and cohort required')
        receipt=receipts.get((label.submission_hash,label.reviewer_id,label.evidence_ref))
        if receipt is not None and label.case_id in receipt.get('case_ids',[]): accepted.append(label)
    decisions_by_id={}
    identities=set()
    for decision in decisions:
        if decision.get('rubric_hash')!=rubric: raise ValueError('judge rubric changed; new evaluator identity required')
        if decision['case_id'] not in required: raise ValueError('judge case not in frozen blind pack')
        if decision.get('status') not in {'PASS','FAIL','PARTIAL','INCOMPLETE'}: raise ValueError('unknown judge status')
        if not decision.get('evaluator_identity'): raise ValueError('judge evaluator identity missing')
        identities.add(decision['evaluator_identity']);decisions_by_id[decision['case_id']]=decision
    if len(identities)>1: raise ValueError('mixed evaluator identities cannot form one comparable cohort')
    compared=[l for l in accepted if l.case_id in decisions_by_id]
    hits=sum(l.label==decisions_by_id[l.case_id]['status'] for l in compared)
    critical=sum(l.label=='FAIL' and decisions_by_id[l.case_id]['status']=='PASS' for l in compared)
    missing=sorted(required-{l.case_id for l in accepted})
    judge_missing=sorted(required-set(decisions_by_id))
    disagreements=[{'case_id':l.case_id,'human':l.label,'judge':decisions_by_id[l.case_id]['status'],
        'human_locations':l.defect_locations} for l in compared if l.label!=decisions_by_id[l.case_id]['status']]
    return {'status':'blocked' if not required or missing or judge_missing else 'completed','accepted_human_labels':len(accepted),
        'required_cases':len(required),'missing_human_cases':missing,'missing_judge_cases':judge_missing,
        'agreement':proportion(hits,len(compared)), 'critical_false_accepts':critical,
        'quality_qualified':False,
        'critical_gate_passed':bool(required) and not missing and not judge_missing and critical==0,
        'disagreements':disagreements,'rubric_hash':rubric,
        'evaluator_identity':next(iter(identities)) if identities else None,
        'interval_scope':'Descriptive paired-case agreement; no population accuracy or inter-rater reliability claim.'}


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='action',required=True)
    intake=commands.add_parser('intake')
    intake.add_argument('--submission',type=Path,required=True)
    intake.add_argument('--review-manifest',type=Path,required=True)
    intake.add_argument('--output',type=Path,required=True)
    intake.add_argument('--reviewer-id',required=True)
    intake.add_argument('--evidence-ref',required=True)
    compare=commands.add_parser('compare')
    for name in ['labels','receipt','decisions','review-manifest','output']:
        compare.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    manifest=json.loads(ordinary_file(args.review_manifest).read_text(encoding='utf-8'))
    if args.action=='intake':
        result=intake_human_submission(args.submission,args.output,reviewer_id=args.reviewer_id,
            evidence_ref=args.evidence_ref,review_manifest=manifest)
    else:
        def jsonl(path): return [json.loads(line) for line in ordinary_file(path).read_text(encoding='utf-8').splitlines() if line.strip()]
        result=compare_human_labels(jsonl(args.labels),jsonl(args.decisions),review_manifest=manifest,
            submission_receipts=[json.loads(ordinary_file(args.receipt).read_text(encoding='utf-8'))])
        with args.output.open('x',encoding='utf-8') as stream: json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False))
    return 1 if result.get('status')=='blocked' else 0


if __name__=='__main__': raise SystemExit(main())
