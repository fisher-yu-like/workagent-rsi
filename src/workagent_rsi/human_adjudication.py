"""Receive human revisions after diagnostic disclosure, separate from blind labels."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .hashing import canonical_json_hash, sha256_file
from .human_calibration import HumanLabel
from .view_safety import ordinary_file, relative_reference


class AdjudicatedLabel(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    case_id: str=Field(min_length=1)
    reviewer_id: str=Field(min_length=1)
    label: Literal['PASS','FAIL','PARTIAL','INCOMPLETE']
    defect_locations: list[str]=Field(min_length=1)
    requirements_checked: Literal[True]
    timestamp: datetime

    @field_validator('requirements_checked',mode='before')
    @classmethod
    def explicit_check(cls,value):
        if value is not True:raise ValueError('explicit requirements-check confirmation required')
        return value

    @field_validator('reviewer_id')
    @classmethod
    def reviewer(cls,value):
        if not value.strip():raise ValueError('reviewer must be nonblank')
        return HumanLabel.actual_reviewer(value)

    @field_validator('timestamp')
    @classmethod
    def aware(cls,value):
        if value.utcoffset() is None:raise ValueError('adjudication timestamp needs a timezone')
        return value

    @field_validator('defect_locations')
    @classmethod
    def reasons(cls,value):
        if any(not text.strip() for text in value):raise ValueError('each adjudication needs a nonempty reason')
        return value


class AdjudicationSubmission(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    schema_version: Literal['office-human-adjudication-v1']
    source_kind: Literal['human_adjudication']
    rubric_hash: str=Field(pattern=r'^[0-9a-f]{64}$')
    source_submission_hash: str=Field(pattern=r'^[0-9a-f]{64}$')
    request_manifest_hash: str=Field(pattern=r'^[0-9a-f]{64}$')
    adjudication_after_diagnostics: Literal[True]
    independent_blind_review: Literal[False]
    labels: list[AdjudicatedLabel]=Field(min_length=1)

    @field_validator('adjudication_after_diagnostics','independent_blind_review',mode='before')
    @classmethod
    def exact_boolean(cls,value,info):
        expected=info.field_name=='adjudication_after_diagnostics'
        if type(value) is not bool or value is not expected:
            raise ValueError('adjudication must declare diagnostic disclosure and nonblind status')
        return value


def intake_adjudication(submission,output,*,request_file,original_intake,public_root,evidence_ref):
    """Controller must have observed the user's actual external file/message.

    Exported fields alone cannot authenticate a reviewer. Revisions are never
    passed through HumanLabel or counted as new independent blind observations.
    """
    if not evidence_ref.strip():raise ValueError('actual external file/message reference required')
    submission=ordinary_file(Path(submission))
    if submission.stat().st_size>1048576:raise ValueError('adjudication exceeds1MB')
    raw=submission.read_bytes();payload=AdjudicationSubmission.model_validate_json(raw)
    request_file=ordinary_file(Path(request_file))
    request=json.loads(request_file.read_text(encoding='utf-8'))
    binding=canonical_json_hash({k:v for k,v in request.items() if k!='request_manifest_hash'})
    if request.get('request_manifest_hash')!=binding or payload.request_manifest_hash!=binding:
        raise ValueError('adjudication request binding changed')
    original=Path(original_intake)
    receipt=json.loads(ordinary_file(original/'submission-receipt.json').read_text(encoding='utf-8'))
    original_hash=sha256_file(ordinary_file(original/'external-submission.json'))
    if not (original_hash==receipt['submission_hash']==payload.source_submission_hash==request['source_submission_hash']):
        raise ValueError('original submission binding changed')
    if not (payload.rubric_hash==request['rubric_hash']==receipt['rubric_hash']):
        raise ValueError('adjudication rubric changed')
    ids=[r.case_id for r in payload.labels]
    required=request['case_ids']
    if len(set(ids))!=len(ids) or len(set(required))!=len(required) or set(ids)!=set(required):
        raise ValueError('adjudication requires each requested case exactly once')
    if len({r.reviewer_id for r in payload.labels})!=1:raise ValueError('mixed adjudication reviewers')
    original_labels=[HumanLabel.model_validate_json(line) for line in ordinary_file(original/'human-labels.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    lookup={r.case_id:r for r in original_labels}
    parent_payload=json.loads((original/'external-submission.json').read_bytes())
    parent_rows={r['case_id']:r for r in parent_payload['labels']}
    if (len(lookup)!=len(original_labels) or set(lookup)!=set(parent_rows)
            or any(r.label!=parent_rows[c]['label'] or r.defect_locations!=parent_rows[c].get('defect_locations',[])
                   or r.submission_hash!=original_hash for c,r in lookup.items())):
        raise ValueError('normalized original labels differ from frozen submission')
    if not set(ids)<=set(lookup):
        raise ValueError('adjudication has no matching original label')
    for name,digest in request['asset_bindings'].items():
        if sha256_file(ordinary_file(Path(public_root)/relative_reference(name)))!=digest:
            raise ValueError('reviewed source artifact/page changed')
    digest=sha256_file(submission)
    rows=[{**r.model_dump(mode='json'),'source_kind':'human_adjudication',
        'submission_hash':digest,'evidence_ref':evidence_ref,'rubric_hash':payload.rubric_hash,
        'original_label':lookup[r.case_id].label,'source_submission_hash':original_hash,
        'independent_blind_review':False} for r in payload.labels]
    result={'schema_version':'human-adjudication-receipt-v1','source_kind':'human_adjudication',
        'submission_hash':digest,'request_manifest_hash':binding,'request_file_sha256':sha256_file(request_file),
        'source_submission_hash':original_hash,'rubric_hash':payload.rubric_hash,
        'reviewer_id':payload.labels[0].reviewer_id,'case_ids':ids,'evidence_ref':evidence_ref,
        'received_at':datetime.now(timezone.utc).isoformat(),'accepted_adjudications':len(rows),
        'label_counts':dict(Counter(r['label'] for r in rows)),
        'changed_from_original':sum(r['label']!=r['original_label'] for r in rows),
        'adjudication_after_diagnostics':True,'independent_blind_review':False,
        'new_independent_blind_labels':0,'original_labels_rewritten':False,
        'reference_gate_passed':False,'quality_qualified':False,
        'scope':'Requirements-checked revisions of a selected subset after diagnostic hints; no full-cohort truth or evaluator-accuracy claim.'}
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    (output/'external-submission.json').write_bytes(raw)
    with (output/'adjudicated-labels.jsonl').open('x',encoding='utf-8') as stream:
        for row in rows:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    (output/'submission-receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result
