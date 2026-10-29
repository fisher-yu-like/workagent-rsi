import pytest

from workagent_rsi.hashing import sha256_file
from workagent_rsi.review_audit import audit_review_pack, compare_standard_reference


def test_same_wording_is_separate_from_duplicate_outputs(tmp_path):
    (tmp_path/'input.xlsx').write_bytes(b'same input')
    for name,body in [('one.xlsx',b'correct'),('two.xlsx',b'defective')]:
        (tmp_path/name).write_bytes(body)
    cases=[dict(case_id=name,domain='excel',instruction='Keep all rows.',artifact=name,
        artifact_hash=sha256_file(tmp_path/name),inputs=['input.xlsx'],cohort='standards-12')
        for name in ('one.xlsx','two.xlsx')]
    manifest={'case_ids':[r['case_id'] for r in cases],'cases':cases}
    report=audit_review_pack(manifest,tmp_path)
    assert report['shared_instruction_case_count']==2
    assert report['identical_artifact_groups']==[]
    (tmp_path/'two.xlsx').write_bytes(b'changed')
    with pytest.raises(ValueError,match='changed'):audit_review_pack(manifest,tmp_path)


def test_standard_triage_does_not_invent_natural_truth_or_relabel():
    labels=[dict(case_id='standard',label='PASS'),dict(case_id='natural',label='PASS')]
    key={'cases':[dict(case_id='standard',original_id='known-defect',cohort='standards-12',oracle='FAIL'),
                  dict(case_id='natural',original_id='model-output',cohort='natural-blind',oracle=None)]}
    report=compare_standard_reference(labels,key)
    assert report['compared_standards']==1 and report['different_labels']==1
    assert report['labels_changed'] is False and not report['quality_qualified']
    assert labels[0]['label']=='PASS'
