"""Audit review-pack repetition without changing frozen files or human labels."""
from collections import defaultdict
import unicodedata
from pathlib import Path

from .hashing import canonical_json_hash, sha256_file
from .view_safety import ordinary_file, relative_reference


def audit_review_pack(manifest, public_root):
    root=Path(public_root)
    rows=manifest['cases']
    ids=[r['case_id'] for r in rows]
    if len(ids)!=len(set(ids)) or set(ids)!=set(manifest['case_ids']):
        raise ValueError('review case identities are not unique and complete')
    instructions,artifacts,identical=defaultdict(list),defaultdict(list),defaultdict(list)
    for row in rows:
        artifact=ordinary_file(root/relative_reference(row['artifact']))
        digest=sha256_file(artifact)
        if digest!=row['artifact_hash']:
            raise ValueError('frozen review artifact changed')
        text=' '.join(unicodedata.normalize('NFKC',row['instruction']).split())
        inputs=sorted(sha256_file(ordinary_file(root/relative_reference(p))) for p in row['inputs'])
        entry={'case_id':row['case_id'],'domain':row['domain'],'cohort':row['cohort'],
               'artifact_hash':digest,'input_hashes':inputs}
        instructions[text].append(entry);artifacts[digest].append(row['case_id'])
        identical[canonical_json_hash([text,inputs,digest])].append(row['case_id'])
    groups=[{'instruction':text,'count':len(entries),'cases':entries}
            for text,entries in instructions.items() if len(entries)>1]
    return {'schema_version':'review-repetition-audit-v1','case_count':len(rows),
        'distinct_instruction_count':len(instructions),'shared_instruction_groups':groups,
        'shared_instruction_case_count':sum(g['count'] for g in groups),
        'identical_artifact_groups':[values for values in artifacts.values() if len(values)>1],
        'identical_task_input_artifact_groups':[values for values in identical.values() if len(values)>1],
        'interpretation':'Shared wording is not an independent task count. Standard variants and benchmark templates must be grouped by family; inspect each input/artifact separately.'}


def compare_standard_reference(labels, case_key):
    """Controlled fixture reference is distinct from a live judge decision."""
    lookup={r['case_id']:r for r in labels}
    if len(lookup)!=len(labels):raise ValueError('duplicate human labels')
    rows=[]
    for case in case_key['cases']:
        if case['cohort']!='standards-12':continue
        if case['case_id'] not in lookup:continue
        label=lookup[case['case_id']]
        rows.append({'case_id':case['case_id'],'original_id':case['original_id'],
            'human_label':label['label'],'standard_reference':case['oracle'],
            'needs_review':label['label']!=case['oracle'],
            'human_notes':label.get('defect_locations',[])})
    return {'scope':'Controlled-standard triage, not live model judging or evaluator accuracy',
        'compared_standards':len(rows),'different_labels':sum(r['needs_review'] for r in rows),
        'rows':rows,'labels_changed':False,'quality_qualified':False}
