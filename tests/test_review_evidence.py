import json

import pytest
from openpyxl import Workbook

from workagent_rsi.hashing import sha256_file
from workagent_rsi.review_evidence import prepare_file_evidence


@pytest.mark.parametrize('suffix',['.txt','.md','.json'])
def test_mixed_text_sources_have_exact_complete_slices(tmp_path,suffix):
    path=tmp_path/('source'+suffix)
    text=json.dumps({'public':'a'*90_000}) if suffix=='.json' else 'Public source\n'*7000
    path.write_text(text,encoding='utf-8',newline='')
    before=sha256_file(path);row=prepare_file_evidence(path,'input-1')
    items=[i for part in row['partition']['partitions'] for i in part['items']]
    assert ''.join(i['text'] for i in items)==text
    assert len(items)>1 and row['text_partition_complete']
    assert sha256_file(path)==before==row['sha256']
    assert not row['native_coverage_qualified']


def test_large_workbook_is_partitioned_without_writing_or_claiming_recalculation(tmp_path):
    path=tmp_path/'large.xlsx';book=Workbook()
    for n in range(1,3001):book.active.cell(n,1,'public-value-'+str(n))
    book.active['B1']='=SUM(A1:A3000)';book.save(path)
    before=sha256_file(path);row=prepare_file_evidence(path,'output')
    assert row['extracted_items']>3000 and row['text_partition_complete']
    assert len(row['partition']['partitions'])>1
    assert any('not recalculated' in s for s in row['limitations'])
    assert sha256_file(path)==before


def test_budget_and_malformed_sources_fail_instead_of_truncating(tmp_path):
    path=tmp_path/'input.txt';path.write_text('large source',encoding='utf-8')
    with pytest.raises(ValueError,match='byte budget'):prepare_file_evidence(path,'input',max_bytes=2)
    with pytest.raises(ValueError,match='character budget'):prepare_file_evidence(path,'input',max_chars=2)
    path=tmp_path/'input.json';path.write_text('{broken',encoding='utf-8')
    with pytest.raises(ValueError):prepare_file_evidence(path,'input')


def test_file_change_rejects_evidence(tmp_path,monkeypatch):
    from workagent_rsi import review_evidence
    path=tmp_path/'input.txt';path.write_text('source',encoding='utf-8')
    original=review_evidence.partition_evidence
    def changed(*args,**kwargs):
        path.write_text('changed',encoding='utf-8')
        return original(*args,**kwargs)
    monkeypatch.setattr(review_evidence,'partition_evidence',changed)
    with pytest.raises(ValueError,match='changed'):prepare_file_evidence(path,'input')
