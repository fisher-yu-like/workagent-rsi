"""Prepare pinned public benchmarks locally; never invoke agents or judges."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from workagent_rsi.benchmark_corpus import (checked_member, extract_archive, file_ref,
    spreadsheet1_tasks, spreadsheet2_tasks, workspace_tasks, freeze_development_splits)
from workagent_rsi.hashing import sha256_file, canonical_json_hash

DEFAULT_LOCK = ROOT / 'project_artifacts/phase3_experiments/configs/benchmark_sources_v1.json'


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def download(url: str, target: Path, *, size: int, sha256: str | None = None,
             blob_sha1: str | None = None, max_seconds: int = 240) -> dict:
    if not url.startswith(('https://huggingface.co/', 'https://raw.githubusercontent.com/')):
        raise ValueError('source must be an admitted official HTTPS origin')
    if not sha256 and not blob_sha1:
        raise ValueError('upstream content identity is required')
    if size < 0 or size > 160_000_000:
        raise ValueError('source exceeds per-file storage budget')
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.part')
    existed = target.exists()
    digest = hashlib.sha256()
    blob = hashlib.sha1(('blob ' + str(size) + '\0').encode())
    total = 0
    started = time.monotonic()
    response = target.open('rb') if existed else urlopen(Request(url, headers={'User-Agent': 'WorkAgent-RSI-benchmark-intake'}), timeout=40)
    try:
        dest = None if existed else temporary.open('xb')
        try:
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > size or time.monotonic() - started > max_seconds:
                    raise ValueError('download exceeded declared size/time budget')
                digest.update(chunk)
                blob.update(chunk)
                if dest is not None:
                    dest.write(chunk)
        finally:
            if dest is not None:
                dest.close()
        if total != size or (sha256 and digest.hexdigest() != sha256) or (blob_sha1 and blob.hexdigest() != blob_sha1):
            raise ValueError('upstream content identity mismatch')
        if not existed:
            temporary.replace(target)
    except BaseException:
        if not existed:
            temporary.unlink(missing_ok=True)
        raise
    finally:
        response.close()
    return {'url': url, 'size_bytes': total, 'sha256': digest.hexdigest(),
            'upstream_blob_sha1': blob_sha1, 'cache_reused': existed}


def extract_checked(archive: Path, target: Path):
    receipt = target.with_name(target.name + '.extraction.json')
    if target.exists():
        record = json.loads(receipt.read_text(encoding='utf-8'))
        actual = {p.relative_to(target).as_posix(): sha256_file(p) for p in target.rglob('*') if p.is_file()}
        if record['archive_sha256'] != sha256_file(archive) or actual != record['files']:
            raise ValueError('extracted source cache changed')
        return record
    record = extract_archive(archive, target)
    record['files'] = {p.relative_to(target).as_posix(): sha256_file(p) for p in target.rglob('*') if p.is_file()}
    write(receipt, record)
    return record


def workspace_inputs(tasks: list[dict], source: dict, cache: Path, *, max_bytes: int) -> dict:
    """Fetch only selected source files, not the 18.7 GB full workspace archive."""
    admitted = [t for t in tasks if t['domain'] in ('word', 'powerpoint', 'excel')]
    revision = source['revision']
    api_root = f'https://huggingface.co/api/datasets/Workspace-Bench/Workspace-Bench/tree/{revision}/'
    resolve_root = f'https://huggingface.co/datasets/Workspace-Bench/Workspace-Bench/resolve/{revision}/'
    def inventory(task):
        directory = 'task_clean_en/' + task['native_id'] + '/data'
        url = api_root + quote(directory, safe='/') + '?limit=1000'
        with urlopen(url, timeout=30) as response:
            if response.headers.get('Link'):
                raise ValueError('task input inventory was paginated; refuse a partial manifest')
            files = json.load(response)
        by_name = {PurePath(x['path']): x for x in files if x['type'] == 'file'}
        selected = []
        for item in task['data_manifest']:
            name = PurePath(item['stored_relpath'])
            if name not in by_name:
                raise ValueError('metadata input absent from pinned task directory: ' + task['base_task_id'])
            entry = by_name[name]
            selected.append((item, entry))
        return task, selected
    # Inspect every size before starting any input download.
    with ThreadPoolExecutor(max_workers=4) as pool:
        inventories = list(pool.map(inventory, admitted))
    required = sum(entry['size'] for _, rows in inventories for _, entry in rows)
    if required > max_bytes:
        raise ValueError('workspace subset exceeds local storage budget')
    receipts = []
    failures = []
    for task, rows in inventories:
        refs = []
        try:
            for item, entry in rows:
                path = checked_member(entry['path'])
                record = download(resolve_root + quote(path, safe='/'), cache / path, size=entry['size'],
                    sha256=entry.get('lfs', {}).get('oid'), blob_sha1=None if entry.get('lfs') else entry['oid'], max_seconds=90)
                receipts.append(record)
                ref = file_ref(cache / path, cache)
                execution_path = checked_member(item['filename'])
                ref['execution_path'] = execution_path
                refs.append(ref)
            task['variants'] = [{'variant_id': task['base_task_id'] + '/native-1', 'inputs': refs}]
            task['context_scope'] = 'task-referenced-files-only; full-workspace search difficulty changed'
        except Exception as exc:
            task['input_status'] = 'unavailable'
            failures.append({'base_task_id': task['base_task_id'], 'error': str(exc)})
    return {'selected_office_tasks': len(admitted), 'planned_bytes': required,
            'downloaded_files': len(receipts), 'receipts': receipts, 'failures': failures,
            'full_workspace_downloaded': False}


def PurePath(value):
    from pathlib import PurePosixPath
    return PurePosixPath(value).name


def prepare(lock_path: Path, cache: Path, output: Path, *, fetch_workspace: bool) -> dict:
    if output.exists():
        raise FileExistsError(output)
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    receipts = {}
    for source in lock['sources']:
        if not source.get('data_license') or source['license_status'] != 'verified':
            raise ValueError('source license is not admitted')
        for asset in source['assets']:
            target = cache / checked_member(asset['local_path'])
            receipts[asset['local_path']] = download(asset['url'], target, size=asset['size_bytes'],
                sha256=asset.get('sha256'), blob_sha1=asset.get('blob_sha1'))
    extract_checked(cache / 'raw/ssb2.zip', cache / 'extracted/ssb2')
    extract_checked(cache / 'raw/ssb1.tar.gz', cache / 'extracted/ssb1')
    by_id = {s['id']: s for s in lock['sources']}
    roots = {'spreadsheetbench-2': cache / 'extracted/ssb2/spreadsheetbench-v2',
             'spreadsheetbench-v1': cache / 'extracted/ssb1/all_data_912_v0.1',
             'workspace-bench-lite': cache / 'workspace-assets'}
    ssb2 = spreadsheet2_tasks(roots['spreadsheetbench-2'], revision=by_id['spreadsheetbench-2']['revision'])
    workspace = workspace_tasks(cache / 'metadata/workspace-lite.csv', cache / 'metadata/workspace-full.csv',
                                revision=by_id['workspace-bench-lite']['revision'])
    ws_report = workspace_inputs(workspace, by_id['workspace-bench-lite'], roots['workspace-bench-lite'],
                                 max_bytes=150_000_000) if fetch_workspace else {'status': 'not_requested'}
    ssb1 = spreadsheet1_tasks(roots['spreadsheetbench-v1'], revision=by_id['spreadsheetbench-v1']['revision'])
    tasks = ssb2 + workspace + ssb1
    report = freeze_development_splits(tasks, seed=lock['seed'])
    report.update({'source_priority': [s['id'] for s in lock['sources']],
        'source_lock_sha256': sha256_file(lock_path), 'model_calls': 0,
        'server_operations': 0, 'native_variant_policy': 'retain existing variants; no synthetic padding',
        'workspace_annotation_bridge': 'Task text, outputs and rubrics exactly match licensed full annotations at all 100 Lite IDs.',
        'workspace_context_differences': sum(t['lite_context_changed'] for t in workspace),
        'workspace_input_report': {k: v for k, v in ws_report.items() if k != 'receipts'},
        'source_counts': {s: {'base_tasks': sum(t['benchmark'] == s for t in tasks),
                             'instances': sum(len(t['variants']) for t in tasks if t['benchmark'] == s)} for s in roots},
        'claim_boundary': 'Exposed adapted development corpus, not official leaderboard results or untouched final data.'})
    # Inputs and hidden evaluation payloads stay outside any candidate export.
    output.mkdir(parents=True)
    write(output / 'evaluator-only/task-manifest.json', {'roots': {s: str(p.resolve()) for s, p in roots.items()}, 'tasks': tasks})
    write(output / 'evaluator-only/download-receipts.json', receipts)
    write(output / 'evaluator-only/workspace-inputs.json', ws_report)
    write(output / 'split-quality-report.json', report)
    write(output / 'run.json', {'command': sys.argv, 'completed_at': datetime.now(timezone.utc).isoformat(),
        'source_hash': sha256_file(Path(__file__)), 'adapter_hash': sha256_file(ROOT / 'src/workagent_rsi/benchmark_corpus.py'),
        'lock_hash': sha256_file(lock_path), 'manifest_hash': canonical_json_hash(tasks),
        'model_calls': 0, 'server_operations': 0})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lock', type=Path, default=DEFAULT_LOCK)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fetch-workspace', action='store_true')
    args = parser.parse_args()
    report = prepare(args.lock, args.cache, args.output, fetch_workspace=args.fetch_workspace)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
