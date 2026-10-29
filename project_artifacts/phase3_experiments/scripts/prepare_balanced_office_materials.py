"""Admit pinned Word inputs and licensed PPT diagram tasks without model calls.

Only public benchmark inputs are downloaded locally. Downloaded source code is
parsed as data or retained as provenance, never executed. No server is used.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from workagent_rsi.benchmark_corpus import file_ref, export_execution_inputs
from workagent_rsi.benchmark_supplement import (parse_word_definitions,
    source_figure_bytes, balanced_candidate_cohort, render_frozen_reference)
from workagent_rsi.hashing import canonical_json_hash, sha256_file
from prepare_benchmark_corpus import download


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def fetch_arxiv(url, target, *, max_bytes=32_000_000):
    if not url.startswith('https://export.arxiv.org/e-print/'):
        raise ValueError('unexpected arXiv origin')
    if target.exists():
        if target.stat().st_size > max_bytes:
            raise ValueError('cached archive exceeds budget')
        return
    partial = target.with_suffix('.part')
    started, count = time.monotonic(), 0
    try:
        with urlopen(Request(url, headers={'User-Agent': 'WorkAgent-RSI/1.0 (local benchmark research)'}), timeout=40) as response, partial.open('xb') as dest:
            while chunk := response.read(1024 * 1024):
                count += len(chunk)
                if count > max_bytes or time.monotonic() - started > 90:
                    raise ValueError('source archive exceeds size/time budget')
                dest.write(chunk)
        partial.replace(target)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def prepare(discovery: Path, pool: Path, output: Path, previous: Path):
    if pool.exists() or output.exists():
        raise FileExistsError('new source pool and output required')
    import pymupdf
    from docx import Document
    pool.mkdir(parents=True)
    word_root, ppt_root = pool / 'word', pool / 'ppt'
    word_root.mkdir(); ppt_root.mkdir()
    word_commit = read(discovery / 'word-commit.json')['sha']
    word_tree = {x['path']: x for x in read(discovery / 'word-tree.json')['tree']}
    definitions = []
    for suite in ('smoke', 'features', 'capabilities'):
        definitions.extend(parse_word_definitions((discovery / f'word-{suite}.ts').read_text(encoding='utf-8')))
    if len(definitions) != 50:
        raise ValueError('frozen Word task count changed')
    receipts = []
    def word_input(name):
        path = 'packages/agent/test/fixtures/' + name
        entry = word_tree[path]
        record = download(f'https://raw.githubusercontent.com/nberk/llm-docx-editing/{word_commit}/{path}',
                          word_root / name, size=entry['size'], blob_sha1=entry['sha'])
        Document(word_root / name)
        return record
    with ThreadPoolExecutor(max_workers=4) as executor:
        receipts.extend(executor.map(word_input, sorted({r['file'] for r in definitions})))
    tasks = []
    for row in definitions:
        base = 'word-edit/' + canonical_json_hash([row['suite'], row['name']])[:20]
        tasks.append({'base_task_id': base, 'benchmark': 'word-editing-benchmark',
            'revision': word_commit, 'domain': 'word', 'category': row['suite'],
            'instruction': row['instruction'], 'execution_mode': 'edit',
            'source_family': 'word-edit/source/' + row['file'],
            'variants': [{'variant_id': base + '/native-1', 'inputs': [file_ref(word_root / row['file'], word_root)]}],
            'private_evaluation': {k: row[k] for k in ('name', 'expectPresent', 'expectAbsent', 'definition_sha256')},
            'scorer': 'upstream-declarative-checks-not-yet-qualified',
            'source_kind': 'external_benchmark_fixture', 'license': 'MIT',
            'source_refs': [f'https://github.com/nberk/llm-docx-editing/tree/{word_commit}'],
            'exposure': 'exposed', 'split': None})
    print(json.dumps({'stage': 'word', 'tasks': len(tasks), 'native_documents': len(receipts)}), flush=True)

    ppt_commit = read(discovery / 'pptbench-commit.json')['sha']
    ppt_tree = {x['path']: x for x in read(discovery / 'pptbench-tree.json')['tree']}
    audit = [json.loads(line) for line in (discovery / 'source_license_audit.jsonl').read_text(encoding='utf-8').splitlines()]
    materialization = {x['task_id']: x for x in map(json.loads, (discovery / 'materialization_manifest.jsonl').read_text(encoding='utf-8').splitlines())}
    eligible = sorted((r for r in audit if r['release_status'] == 'release-ready'
        and r['redistribution_grant'] is True and r['license_family'] in {'cc-by', 'cc-by-sa', 'cc0'}
        and not materialization[r['task_id']]['resources']
        and materialization[r['task_id']]['source']['filename'].lower().endswith('.pdf')),
        key=lambda r: r['task_id'])
    failures, admitted = [], []
    # Source availability is recorded, never a model-success selection. At most
    # 48 predefined candidates, 24 admitted inputs and600MB cached archives.
    archives = pool / 'source-archives'; archives.mkdir()
    trial = discovery / 'trial-arxiv-source.tar'
    last_request = 0.0
    for license_row in eligible[:48]:
        if len(admitted) == 24:
            break
        identity = license_row['task_id']
        frozen = materialization[identity]
        folder = ppt_root / identity; folder.mkdir()
        metadata_path = f'benchmark/tasks/{identity}/metadata.json'
        entry = ppt_tree[metadata_path]
        try:
            record = download(f'https://raw.githubusercontent.com/Einsia/PPTBench/{ppt_commit}/{metadata_path}',
                folder / 'upstream-metadata.json', size=entry['size'], blob_sha1=entry['sha'])
            receipts.append(record)
            metadata = read(folder / 'upstream-metadata.json')
            if metadata['paper']['versioned_id'] != license_row['versioned_id']:
                raise ValueError('source license version differs')
            archive = archives / (license_row['versioned_id'] + '.tar')
            if identity == 'task_0000' and trial.exists():
                import shutil
                shutil.copyfile(trial, archive)
            else:
                pause = 3.1 - (time.monotonic() - last_request)
                if pause > 0:
                    time.sleep(pause)
                last_request = time.monotonic()
                fetch_arxiv(frozen['source']['archive_url'], archive)
            if sum(p.stat().st_size for p in archives.iterdir()) > 600_000_000:
                raise RuntimeError('total local archive budget exhausted')
            body = source_figure_bytes(archive, frozen['source']['filename'], frozen['source']['sha256'])
            pdf = folder / 'source-figure.pdf'; pdf.write_bytes(body)
            png = folder / 'reference.png'
            pixel_hash = render_frozen_reference(pdf, frozen['reference'], png)
            license_file = folder / 'attribution.json'; write(license_file, license_row)
            base = 'pptbench/' + identity
            instruction = ('Reconstruct the supplied scientific diagram as one editable PowerPoint slide. '
                'Preserve its text, nodes, connectors, spatial relationships and process semantics. '
                'Use native editable text, shapes and connectors; do not embed the entire reference '
                'image or PDF as a flat slide. No external raster resources are authorized for this task. '
                'Save the result as output.pptx. Source caption: ' + metadata.get('caption', ''))
            task = {'base_task_id': base, 'benchmark': 'pptbench-editable-diagrams',
                'revision': ppt_commit, 'domain': 'powerpoint',
                'category': metadata['paper'].get('primary_category', 'scientific-diagram'),
                'instruction': instruction, 'execution_mode': 'create',
                'source_family': 'arxiv/' + license_row['arxiv_id'],
                'variants': [{'variant_id': base + '/native-1', 'inputs': [
                    file_ref(png, ppt_root), file_ref(pdf, ppt_root), file_ref(license_file, ppt_root)]}],
                'private_evaluation': {'upstream_metadata': metadata, 'source_license': license_row,
                    'materialization': frozen, 'source_archive_sha256': sha256_file(archive),
                    'render_pixel_sha256': pixel_hash,
                    'upstream_reference_pixels_match': pixel_hash == frozen['reference']['pixel_sha256']},
                'scorer': 'adapted-editable-diagram-task-not-native-score',
                'source_kind': 'external_licensed', 'license': license_row['license_url'],
                'source_refs': [license_row['abs_url'], f'https://github.com/Einsia/PPTBench/tree/{ppt_commit}'],
                'exposure': 'exposed', 'split': None}
            tasks.append(task); admitted.append(identity)
            print(json.dumps({'stage': 'ppt', 'case': identity, 'admitted': len(admitted),
                              'source_bytes': len(body), 'reference_pixels_match': task['private_evaluation']['upstream_reference_pixels_match']}), flush=True)
        except Exception as exc:
            failures.append({'task_id': identity, 'reason': type(exc).__name__ + ': ' + str(exc)})
            print(json.dumps({'stage': 'ppt', 'case': identity, 'excluded': failures[-1]['reason']}), flush=True)
            if isinstance(exc, RuntimeError):
                break
        write(pool / 'intake-progress.json', {'admitted': admitted, 'failures': failures})
    write(pool / 'evaluator-only/task-manifest.json', {'roots': {
        'word-editing-benchmark': str(word_root.resolve()),
        'pptbench-editable-diagrams': str(ppt_root.resolve())}, 'tasks': tasks})
    write(pool / 'download-receipts.json', receipts)
    write(pool / 'source-admission.json', {'word_tasks': 50, 'word_source_documents': 31,
        'ppt_tasks': len(admitted), 'ppt_eligible_licensed_no_resource_tasks': len(eligible),
        'ppt_availability_exclusions': failures, 'model_calls': 0, 'server_operations': 0,
        'archive_bytes': sum(p.stat().st_size for p in archives.iterdir()),
        'pymupdf_version': pymupdf.VersionBind,
        'word_license_evidence_sha256': sha256_file(discovery / 'word-LICENSE.txt'),
        'ppt_license_audit_sha256': sha256_file(discovery / 'source_license_audit.jsonl')})
    original = read(previous)
    selected, report = balanced_candidate_cohort(original['tasks'] + tasks)
    roots = {**original['roots'], 'word-editing-benchmark': str(word_root.resolve()),
             'pptbench-editable-diagrams': str(ppt_root.resolve())}
    output.mkdir(parents=True)
    write(output / 'evaluator-only/task-manifest.json', {'roots': roots, 'tasks': selected})
    for task in selected:
        export_execution_inputs(task, task['variants'][0]['variant_id'], Path(roots[task['benchmark']]),
                                output / 'execution-views' / task['domain'] / task['base_task_id'].replace('/', '__'))
    report.update(source_pool_manifest=str((pool / 'evaluator-only/task-manifest.json').resolve()),
        prior_reserved_manifest_sha256=sha256_file(previous), model_calls=0, server_operations=0,
        source_counts=dict(Counter(t['benchmark'] for t in selected)),
        execution_exports=len(selected), all_source_files_downloaded_locally=True)
    write(output / 'cohort-report.json', report)
    write(output / 'run.json', {'argv': sys.argv, 'script_sha256': sha256_file(Path(__file__)),
        'adapter_sha256': sha256_file(ROOT / 'src/workagent_rsi/benchmark_supplement.py'),
        'source_pool_manifest_sha256': sha256_file(pool / 'evaluator-only/task-manifest.json'),
        'report_sha256': sha256_file(output / 'cohort-report.json')})
    print(json.dumps(report), flush=True)


def finalize_existing_pool(pool: Path, output: Path, previous: Path):
    """Finalize saved inputs without re-downloading or changing initial evidence."""
    if output.exists():
        raise FileExistsError('new finalized cohort required')
    original_pool = pool / 'evaluator-only/task-manifest.json'
    data = read(original_pool)
    verified = []
    for task in data['tasks']:
        if task['benchmark'] != 'pptbench-editable-diagrams':
            continue
        root = Path(data['roots'][task['benchmark']])
        folder = root / task['base_task_id'].split('/')[-1]
        png = folder / 'reference.frozen.png'
        private = task['private_evaluation']
        digest = render_frozen_reference(folder / 'source-figure.pdf', private['materialization']['reference'], png)
        private.update(render_pixel_sha256=digest, upstream_reference_pixels_match=True)
        refs = task['variants'][0]['inputs']
        refs[0] = file_ref(png, root)
        verified.append(task['base_task_id'])
    frozen_pool = pool / 'evaluator-only/task-manifest.frozen.json'
    if frozen_pool.exists():
        raise FileExistsError('frozen source manifest already exists')
    write(frozen_pool, data)
    original = read(previous)
    selected, report = balanced_candidate_cohort(original['tasks'] + data['tasks'])
    roots = {**original['roots'], **data['roots']}
    output.mkdir(parents=True)
    write(output / 'evaluator-only/task-manifest.json', {'roots': roots, 'tasks': selected})
    for task in selected:
        export_execution_inputs(task, task['variants'][0]['variant_id'], Path(roots[task['benchmark']]),
            output / 'execution-views' / task['domain'] / task['base_task_id'].replace('/', '__'))
    report.update(source_pool_manifest=str(frozen_pool.resolve()), source_pool_manifest_sha256=sha256_file(frozen_pool),
        prior_reserved_manifest_sha256=sha256_file(previous), model_calls=0, server_operations=0,
        source_counts=dict(Counter(t['benchmark'] for t in selected)), execution_exports=len(selected),
        frozen_ppt_reference_pixels_verified=len(verified),
        initial_reference_materialization_superseded=True)
    write(output / 'cohort-report.json', report)
    write(output / 'run.json', {'argv': sys.argv, 'script_sha256': sha256_file(Path(__file__)),
        'adapter_sha256': sha256_file(ROOT / 'src/workagent_rsi/benchmark_supplement.py'),
        'report_sha256': sha256_file(output / 'cohort-report.json'),
        'initial_source_manifest_sha256': sha256_file(original_pool), 'reference_verifications': verified})
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--discovery', type=Path, required=True)
    parser.add_argument('--pool', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--finalize-existing-pool', action='store_true')
    args = parser.parse_args()
    if args.finalize_existing_pool:
        finalize_existing_pool(args.pool, args.output, args.previous)
    else:
        prepare(args.discovery, args.pool, args.output, args.previous)
