"""Licensed benchmark inputs, native variants, and conservative source grouping.

This adapter never supplies reference workbooks or rubrics to the executor.
It does not turn an adapted subset into an official benchmark score, or a
publicly inspected task into an untouched final test.
"""
from __future__ import annotations

from collections import Counter
import csv
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tarfile
import zipfile

from .contracts import TaskSpec
from .hashing import canonical_json_hash, sha256_file
from .view_safety import ordinary_file, relative_reference

DOMAINS = {'.xlsx': 'excel', '.docx': 'word', '.pptx': 'powerpoint'}


def checked_member(name: str) -> str:
    # POSIX archive paths must also be safe on Windows (including ADS/drive paths).
    if not name or '\\' in name or ':' in name:
        raise ValueError('unsafe archive member')
    path = PurePosixPath(name)
    if path.is_absolute() or any(p in ('..', '.') for p in name.split('/')):
        raise ValueError('unsafe archive member')
    return path.as_posix()


def extract_archive(archive: Path, output: Path, *, max_bytes: int = 700_000_000,
                    max_files: int = 20_000) -> dict:
    """Preflight the whole archive before writing; never follow archive links."""
    if output.exists():
        raise FileExistsError(output)
    total = 0
    names = set()
    entries = []
    is_zip = zipfile.is_zipfile(archive)
    container = zipfile.ZipFile(archive) if is_zip else tarfile.open(archive)
    with container:
        for member in container.infolist() if is_zip else container.getmembers():
            raw = member.orig_filename if is_zip else member.name
            name = checked_member(raw.rstrip('/'))
            mode = member.external_attr >> 16 if is_zip else 0
            if (is_zip and stat.S_ISLNK(mode)) or (not is_zip and not (member.isfile() or member.isdir())):
                raise ValueError('archive links and special files are forbidden')
            if name.casefold() in names:
                raise ValueError('duplicate archive member')
            names.add(name.casefold())
            directory = member.is_dir() if is_zip else member.isdir()
            size = member.file_size if is_zip else member.size
            if size < 0:
                raise ValueError('invalid archive size')
            total += size
            entries.append((member, name, directory))
            if total > max_bytes or len(entries) > max_files:
                raise ValueError('archive exceeds storage budget')
        output.mkdir(parents=True)
        for member, name, directory in entries:
            target = output / name
            if directory:
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                source = container.open(member) if is_zip else container.extractfile(member)
                with source, target.open('xb') as dest:
                    shutil.copyfileobj(source, dest, 1024 * 1024)
    return {'archive_sha256': sha256_file(archive), 'entries': len(entries), 'expanded_bytes': total}


def file_ref(path: Path, root: Path) -> dict:
    path = ordinary_file(path)
    return {'path': path.resolve().relative_to(root.resolve()).as_posix(),
            'sha256': sha256_file(path), 'size_bytes': path.stat().st_size}


def _resolve(root: Path, name: str) -> Path:
    relative_reference(name)
    path = ordinary_file(root / name)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('benchmark path escapes data root')
    return path


def spreadsheet2_tasks(root: Path, *, revision: str) -> list[dict]:
    result = []
    for metadata in sorted(root.glob('*/dataset.json')):
        category = metadata.parent.name
        for row in json.loads(metadata.read_text(encoding='utf-8')):
            source = _resolve(metadata.parent, row['spreadsheet_path'])
            gold = _resolve(metadata.parent, row['golden_response_path'])
            native_id = str(row['id'])
            base = f'ssb2/{category}/{native_id}'
            result.append({'base_task_id': base, 'benchmark': 'spreadsheetbench-2',
                'revision': revision, 'native_id': native_id, 'category': category,
                'domain': 'excel', 'instruction': row['instruction'],
                'source_family': f'ssb2/{category}/{PurePosixPath(row["golden_response_path"]).parent}',
                'variants': [{'variant_id': base + '/native-1', 'inputs': [file_ref(source, root)],
                              'reference': file_ref(gold, root)}],
                'private_evaluation': {k: v for k, v in row.items() if k not in ('instruction', 'spreadsheet_path')},
                'scorer': 'native-vlm-windows-com' if category == 'Visualization' else 'native-spreadsheet2',
                'source_kind': 'external_licensed', 'license': 'MIT',
                'source_refs': [f'https://huggingface.co/datasets/KAKA22/SpreadsheetBench-v2/tree/{revision}'],
                'exposure': 'exposed', 'split': None})
    return result


def spreadsheet1_tasks(root: Path, *, revision: str) -> list[dict]:
    result = []
    for row in json.loads((root / 'dataset.json').read_text(encoding='utf-8')):
        folder = root / checked_member(row['spreadsheet_path'])
        native_id = str(row['id'])
        base = 'ssb1/' + native_id
        variants = []
        for source in sorted(folder.glob('*_input.xlsx')):
            gold = ordinary_file(source.with_name(source.name[:-len('_input.xlsx')] + '_answer.xlsx'))
            variants.append({'variant_id': base + '/' + source.name[:-len('_input.xlsx')],
                             'inputs': [file_ref(source, root)], 'reference': file_ref(gold, root)})
        if not variants:
            raise ValueError('native task has no input variants')
        result.append({'base_task_id': base, 'benchmark': 'spreadsheetbench-v1',
            'revision': revision, 'native_id': native_id, 'category': row['instruction_type'],
            'domain': 'excel', 'instruction': row['instruction'], 'source_family': base,
            'variants': variants, 'private_evaluation': {k: v for k, v in row.items() if k != 'instruction'},
            'scorer': 'native-spreadsheet1', 'source_kind': 'external_licensed', 'license': 'CC-BY-SA-4.0',
            'source_refs': [f'https://github.com/RUCKBReasoning/SpreadsheetBench/tree/{revision}'],
            'exposure': 'exposed', 'split': None})
    return result


def workspace_tasks(lite_csv: Path, full_csv: Path, *, revision: str) -> list[dict]:
    """Use Apache-2.0 full-release annotations at the official Lite task IDs.

The Lite card has no license field. Do not infer its asset license from GitHub.
Full task text, outputs and rubrics must match before recording this bridge.
Inputs/graphs always come from that licensed full release; differences from
Lite are retained in the audit, not silently treated as identical contexts.
"""
    def read(path):
        with path.open(encoding='utf-8-sig', newline='') as stream:
            return list(csv.DictReader(stream))
    full = {r['absolute_id']: r for r in read(full_csv)}
    result = []
    for lite in read(lite_csv):
        row = full[lite['absolute_id']]
        if any(json.loads(lite[k]) != json.loads(row[k]) for k in ('output_files', 'rubrics')) or lite['task'] != row['task']:
            raise ValueError('licensed full annotations differ from Lite task')
        outputs = json.loads(row['output_files'])
        domains = {DOMAINS[Path(n).suffix.lower()] for n in outputs if Path(n).suffix.lower() in DOMAINS}
        domain = next(iter(domains)) if len(domains) == 1 else None
        result.append({'base_task_id': 'wbl/' + row['absolute_id'], 'benchmark': 'workspace-bench-lite',
            'revision': revision, 'native_id': row['absolute_id'], 'category': row['persona'],
            'domain': domain, 'instruction': row['task'], 'source_family': 'workspace/' + row['persona'],
            'variants': [], 'output_files': outputs, 'data_manifest': json.loads(row['data_manifest']),
            'private_evaluation': {'rubrics': json.loads(row['rubrics']), 'file_dep_graph': json.loads(row['file_dep_graph'])},
            'lite_context_changed': any(lite[k] != row[k] for k in ('data_manifest', 'file_dep_graph')),
            'scorer': 'workspace-rubric-judge', 'source_kind': 'external_licensed', 'license': 'Apache-2.0',
            'source_refs': [f'https://huggingface.co/datasets/Workspace-Bench/Workspace-Bench/tree/{revision}'],
            'exposure': 'exposed', 'split': None})
    return result


def connected_groups(tasks: list[dict]) -> list[list[dict]]:
    """Shared source families and any identical input/reference are transitive."""
    if len({t['base_task_id'] for t in tasks}) != len(tasks):
        raise ValueError('duplicate benchmark task identity')
    parents = list(range(len(tasks)))
    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    owners = {}
    for i, task in enumerate(tasks):
        keys = ['family:' + task['source_family']]
        for variant in task['variants']:
            keys.extend('content:' + ref['sha256'] for ref in variant['inputs'])
            if variant.get('reference'):
                keys.append('content:' + variant['reference']['sha256'])
        # Also bind unresolved workspace sources before downloads exist.
        for ref in task.get('data_manifest', []):
            prefix = PurePosixPath(ref['stored_relpath']).name.split('_', 1)[0]
            if re.fullmatch('[a-f0-9]{16,64}', prefix):
                keys.append('workspace-source:' + prefix)
        for key in keys:
            if key in owners:
                parents[find(i)] = find(owners[key])
            else:
                owners[key] = i
    groups = {}
    for i, task in enumerate(tasks):
        groups.setdefault(find(i), []).append(task)
    return sorted((sorted(g, key=lambda t: t['base_task_id']) for g in groups.values()),
                  key=lambda g: g[0]['base_task_id'])


def freeze_development_splits(tasks: list[dict], *, seed: int) -> dict:
    """Freeze an exposed benchmark cohort; final_test remains unavailable.

This is a development resource, not a replacement for the original 72/216
three-domain final-set acceptance gate. Whole workspace personas stay together.
"""
    for group in connected_groups(tasks):
        identity = canonical_json_hash(sorted(t['base_task_id'] for t in group))
        bucket = int(canonical_json_hash([seed, identity])[:8], 16) % 10
        split = 'develop' if bucket < 4 else 'regression' if bucket < 6 else 'promotion_validation' if bucket < 8 else 'ood_transfer'
        for task in group:
            task['family_id'] = identity
            task['split'] = split
    by_domain = {d: dict(Counter(t['split'] for t in tasks if t['domain'] == d)) for d in DOMAINS.values()}
    return {'schema_version': 'benchmark-development-splits-v1', 'seed': seed,
            'base_tasks': len(tasks), 'instances': sum(len(t['variants']) for t in tasks),
            'connected_source_groups': len(connected_groups(tasks)), 'per_domain': by_domain,
            'final_test_count': 0, 'untouched_final_claim': False,
            'original_target_base_tasks': 72, 'original_target_instances': 216,
            'original_t26_acceptance': 'blocked',
            'blockers': ['Untouched final corpus and evaluator-side deployment still required.',
                         'Native variants and available Word/PPT families do not satisfy original per-domain targets.'],
            'manifest_hash': canonical_json_hash(tasks)}


def execution_task(task: dict, variant_id: str) -> TaskSpec:
    if task.get('split') == 'final_test':
        raise PermissionError('final tasks require the separate one-use evaluator')
    if task.get('split') is None:
        raise ValueError('freeze source groups before exporting tasks')
    variant = next(v for v in task['variants'] if v['variant_id'] == variant_id)
    return TaskSpec(task_id=variant_id, domain=task['domain'], instruction=task['instruction'],
                    input_files=tuple(r['path'] for r in variant['inputs']),
                    execution_mode='create' if task['benchmark'] == 'workspace-bench-lite' else 'edit')


def export_execution_inputs(task: dict, variant_id: str, source_root: Path, output: Path) -> TaskSpec:
    """Copy only allowlisted inputs with hashes checked again at export time."""
    spec = execution_task(task, variant_id)
    variant = next(v for v in task['variants'] if v['variant_id'] == variant_id)
    inputs = []
    for ref in variant['inputs']:
        source = _resolve(source_root, ref['path'])
        if sha256_file(source) != ref['sha256']:
            raise ValueError('benchmark input hash mismatch')
        inputs.append((ref.get('execution_path', source.name), source))
    if any(n.casefold() == 'task.json' for n, _ in inputs):
        raise ValueError('execution input collides with task metadata')
    if len({n.casefold() for n, _ in inputs}) != len(inputs):
        raise ValueError('execution input name collision')
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    for name, source in inputs:
        relative_reference(name)
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    spec = spec.model_copy(update={'input_files': tuple(n for n, _ in inputs)})
    (output / 'task.json').write_text(spec.model_dump_json(indent=2) + '\n', encoding='utf-8')
    return spec
