"""Small independent controls for external content, leakage and source grouping."""
import csv
import importlib.util
from pathlib import Path
import tarfile
import zipfile

import pytest

from workagent_rsi.benchmark_corpus import (extract_archive, connected_groups,
    freeze_development_splits, execution_task, export_execution_inputs, workspace_tasks)
from workagent_rsi.hashing import sha256_file


@pytest.mark.parametrize('name', ['../escape.xlsx', '/absolute.xlsx', 'C:/drive.xlsx', 'normal.xlsx:stream', 'a\\escape.xlsx'])
def test_archive_rejects_unsafe_paths_before_writing(tmp_path, name):
    archive = tmp_path / 'bad.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('safe.xlsx', b'first')
        z.writestr(name, b'bad')
    # Windows ZipInfo normalizes slashes, including on read. Author raw ZIP
    # name bytes so this exercises a foreign archive, not the local writer.
    if '\\' in name:
        archive.write_bytes(archive.read_bytes().replace(name.replace('\\', '/').encode(), name.encode()))
    with pytest.raises(ValueError, match='unsafe'):
        extract_archive(archive, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_archive_rejects_links_and_declared_expansion(tmp_path):
    archive = tmp_path / 'link.tar'
    with tarfile.open(archive, 'w') as t:
        info = tarfile.TarInfo('link.xlsx')
        info.type = tarfile.SYMTYPE
        info.linkname = 'elsewhere'
        t.addfile(info)
    with pytest.raises(ValueError, match='links'):
        extract_archive(archive, tmp_path / 'out')
    archive = tmp_path / 'large.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('input.xlsx', b'123456789')
    with pytest.raises(ValueError, match='budget'):
        extract_archive(archive, tmp_path / 'out', max_bytes=8)
    assert not (tmp_path / 'out').exists()


def task(name, family, digest):
    return {'base_task_id': name, 'source_family': family, 'domain': 'excel',
            'benchmark': 'spreadsheetbench-2', 'instruction': 'Complete the workbook.',
            'variants': [{'variant_id': name + '/one', 'inputs': [{'path': 'input.xlsx', 'sha256': digest}],
                          'reference': {'path': 'SECRET_GOLD.xlsx', 'sha256': 'f' * 64}}],
            'private_evaluation': {'rubrics': ['SECRET_RUBRIC']}, 'split': None, 'exposure': 'exposed'}


def test_shared_reference_and_transitive_sources_never_cross_splits():
    a, b, c = task('a', 'one', 'a' * 64), task('b', 'two', 'b' * 64), task('c', 'two', 'c' * 64)
    c['variants'][0]['reference']['sha256'] = 'e' * 64
    rows = [a, b, c]
    assert len(connected_groups(rows)) == 1
    report = freeze_development_splits(rows, seed=13)
    assert len({t['split'] for t in rows}) == 1
    assert report['final_test_count'] == 0
    assert report['original_t26_acceptance'] == 'blocked'
    spec = execution_task(a, 'a/one')
    assert 'SECRET' not in spec.model_dump_json()
    assert spec.expected_constraints == {}


def test_export_copies_only_input_and_detects_tampering(tmp_path):
    source = tmp_path / 'data'
    source.mkdir()
    (source / 'input.xlsx').write_bytes(b'original public input')
    (source / 'SECRET_GOLD.xlsx').write_bytes(b'hidden oracle')
    t = task('a', 'one', sha256_file(source / 'input.xlsx'))
    freeze_development_splits([t], seed=13)
    out = tmp_path / 'executor'
    export_execution_inputs(t, 'a/one', source, out)
    assert sorted(p.name for p in out.iterdir()) == ['input.xlsx', 'task.json']
    assert 'SECRET' not in (out / 'task.json').read_text()
    (source / 'input.xlsx').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='hash'):
        export_execution_inputs(t, 'a/one', source, tmp_path / 'another')
    assert not (tmp_path / 'another').exists()
    t['split'] = 'final_test'
    with pytest.raises(PermissionError, match='final'):
        execution_task(t, 'a/one')


def test_workspace_license_bridge_requires_matching_annotations(tmp_path):
    row = {'absolute_id': '1', 'persona': 'Researcher', 'task': 'Write the report.',
           'output_files': '["report.docx"]', 'rubrics': '["Covers the source facts"]',
           'file_dep_graph': '[]', 'data_manifest': '[]'}
    def write(path, item):
        with path.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(item))
            writer.writeheader()
            writer.writerow(item)
    lite, full = tmp_path / 'lite.csv', tmp_path / 'full.csv'
    write(lite, row)
    write(full, row)
    records = workspace_tasks(lite, full, revision='pinned')
    assert records[0]['domain'] == 'word'
    assert records[0]['license'] == 'Apache-2.0'
    write(full, {**row, 'rubrics': '["A different requirement"]'})
    with pytest.raises(ValueError, match='annotations differ'):
        workspace_tasks(lite, full, revision='pinned')


def test_task_metadata_cannot_overwrite_an_authorized_input(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'task.json').write_text('source data')
    t = task('a', 'one', sha256_file(source / 'task.json'))
    t['variants'][0]['inputs'][0]['path'] = 'task.json'
    freeze_development_splits([t], seed=13)
    with pytest.raises(ValueError, match='collides'):
        export_execution_inputs(t, 'a/one', source, tmp_path / 'export')
    assert not (tmp_path / 'export').exists()


def test_bounded_download_refuses_corrupt_cached_sources(tmp_path):
    path = Path(__file__).parents[1] / 'project_artifacts/phase3_experiments/scripts/prepare_benchmark_corpus.py'
    spec = importlib.util.spec_from_file_location('benchmark_prepare', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cached = tmp_path / 'archive.zip'
    cached.write_bytes(b'bad')
    with pytest.raises(ValueError, match='identity mismatch'):
        module.download('https://huggingface.co/datasets/test/resolve/pinned/archive.zip', cached,
                        size=3, sha256='0' * 64)
    assert cached.read_bytes() == b'bad'
