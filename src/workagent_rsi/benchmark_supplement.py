"""External task literals and a balanced, exposed development candidate cohort.

Downloaded benchmark code is never imported. Source figures remain hash-bound
inputs; source checklists stay private. This module cannot qualify a final set.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

from .benchmark_corpus import checked_member, connected_groups
from .hashing import canonical_json_hash


def _string_literal(value: str) -> str:
    value = value.strip().rstrip(',').strip()
    if value.startswith('"'):
        result = json.loads(value)
        if not isinstance(result, str):
            raise ValueError('expected a string literal')
        return result
    if not value.startswith('`') or not value.endswith('`') or '${' in value:
        raise ValueError('executable expression is not a task literal')
    body = value[1:-1]
    # Support only the escape forms present in the frozen source definitions.
    if re.search(r'\\(?![\\`"nrt])', body):
        raise ValueError('unsupported task string escape')
    return re.sub(r'\\([\\`"nrt])', lambda m: {
        'n': '\n', 'r': '\r', 't': '\t'}.get(m[1], m[1]), body)


def parse_word_definitions(source: str) -> list[dict]:
    """Read the pinned benchmark's declarative TS objects without running JS."""
    blocks = re.findall(r'^  \{\s*\n(.*?)^  \},', source, re.M | re.S)
    expected = len(re.findall(r'^    name:', source, re.M))
    if not blocks or len(blocks) != expected:
        raise ValueError('unsupported task-definition layout')
    result = []
    for block in blocks:
        row = {}
        for key in ('name', 'file', 'instruction', 'suite'):
            match = re.search(r'^    ' + key + r':\s*("(?:\\.|[^"\\])*"|`(?:\\.|[^`\\])*`),?\s*$',
                              block, re.M | re.S if key == 'instruction' else re.M)
            if match is None:
                raise ValueError('task literal missing or expression used: ' + key)
            row[key] = _string_literal(match[1])
        for key in ('expectPresent', 'expectAbsent'):
            match = re.search(r'^    ' + key + r':\s*(\[[^\n]*\]),', block, re.M)
            if match is None:
                raise ValueError('private expected-check literals missing')
            row[key] = json.loads(match[1])
            if not all(isinstance(v, str) for v in row[key]):
                raise ValueError('expected checks must be strings')
        checked_member(row['file'])
        row['definition_sha256'] = hashlib.sha256(block.encode('utf-8')).hexdigest()
        result.append(row)
    return result


def source_figure_bytes(archive: Path, filename: str, digest: str,
                        *, max_bytes: int = 16_000_000) -> bytes:
    """Read only a named regular member. Never extract or run an arXiv archive."""
    checked_member(filename)
    candidates = []
    total, members = 0, 0
    with tarfile.open(archive, 'r:*') as tar:
        for member in tar:
            total += member.size
            members += 1
            if total > 256_000_000 or members > 10000:
                raise ValueError('source archive expansion budget exceeded')
            if PurePosixPath(member.name).name != PurePosixPath(filename).name:
                continue
            checked_member(member.name.removeprefix('./'))
            if not member.isfile() or member.size > max_bytes:
                raise ValueError('source figure is not a bounded ordinary file')
            stream = tar.extractfile(member)
            if stream is None:
                raise ValueError('source figure cannot be read')
            with stream:
                body = stream.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise ValueError('source figure exceeds budget')
            if hashlib.sha256(body).hexdigest() == digest:
                candidates.append(body)
    if len(candidates) != 1:
        raise ValueError('source figure missing, ambiguous or hash mismatch')
    return candidates[0]


def render_frozen_reference(pdf: Path, specification: dict, output: Path) -> str:
    """Match upstream PyMuPDF alpha compositing and dimension-bound pixel hash."""
    import pymupdf
    from PIL import Image
    with pymupdf.open(pdf) as document:
        if len(document) != 1:
            raise ValueError('figure source must contain one page')
        page = document[0]
        scale = min(specification['maximum_scale'],
                    specification['maximum_side'] / max(page.rect.width, page.rect.height))
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=True)
    rgba = Image.frombytes('RGBA', (pixmap.width, pixmap.height), pixmap.samples)
    image = Image.alpha_composite(Image.new('RGBA', rgba.size, 'white'), rgba).convert('RGB')
    digest = hashlib.sha256(b'RGB\0' + image.width.to_bytes(8, 'big')
                            + image.height.to_bytes(8, 'big') + image.tobytes()).hexdigest()
    if digest not in {specification.get('pixel_sha256'), specification.get('historic_pixel_sha256')}:
        raise ValueError('rendered reference pixels differ from frozen benchmark')
    image.save(output)
    return digest


def balanced_candidate_cohort(tasks: list[dict], *, per_domain: int = 24,
                              seed: int = 20261026) -> tuple[list[dict], dict]:
    """Select one task per connected family and one original variant per task.

    Include the old reserved tasks in the input pool so shared files and
    transitive source-family links are excluded before selection.
    """
    if per_domain < 1:
        raise ValueError('positive per-domain target required')
    groups = connected_groups(tasks)
    excluded = 0
    pools = {d: [] for d in ('excel', 'word', 'powerpoint')}
    for group in groups:
        if any(t.get('split') in {'human_calibration', 'final_test'} for t in group):
            excluded += len(group)
            continue
        if len({t['domain'] for t in group}) != 1:
            continue
        domain = group[0]['domain']
        if domain not in pools:
            continue
        eligible = [t for t in group if t.get('variants')]
        if not eligible:
            continue
        identity = canonical_json_hash(sorted(t['base_task_id'] for t in group))
        priority = {'spreadsheetbench-2': 0, 'word-editing-benchmark': 0,
                    'pptbench-editable-diagrams': 0, 'spreadsheetbench-v1': 2}
        choice = min(eligible, key=lambda t: (priority.get(t['benchmark'], 1),
                      canonical_json_hash([seed, t['base_task_id']])))
        pools[domain].append((identity, choice))
    for domain, pool in pools.items():
        if len(pool) < per_domain:
            raise ValueError(f'insufficient independent {domain} families: {len(pool)}/{per_domain}')
    selected = []
    for domain, pool in pools.items():
        pool.sort(key=lambda item: (0 if item[1]['benchmark'] == 'spreadsheetbench-2' else 1,
                                   canonical_json_hash([seed, domain, item[0]])))
        for i, (identity, original) in enumerate(pool[:per_domain]):
            task = deepcopy(original)
            task['family_id'] = identity
            task['variants'] = [sorted(task['variants'], key=lambda v: v['variant_id'])[0]]
            # No final allocation is possible for these inspected public tasks.
            if per_domain == 24:
                task['split'] = ('develop' if i < 8 else 'regression' if i < 16
                                 else 'promotion_validation' if i < 20 else 'ood_transfer')
            else:
                task['split'] = 'develop'
            task['exposure'] = 'exposed'
            selected.append(task)
    selected.sort(key=lambda t: (t['domain'], t['base_task_id']))
    counts = dict(Counter(t['domain'] for t in selected))
    return selected, {'schema_version': 'balanced-office-candidate-cohort-v1',
        'per_domain_base_tasks': counts, 'base_tasks': len(selected),
        'native_input_instances': len(selected), 'connected_source_groups': len(selected),
        'per_domain_splits': {d: dict(Counter(t['split'] for t in selected if t['domain'] == d)) for d in pools},
        'seed': seed, 'max_domain_count_ratio': max(counts.values()) / min(counts.values()),
        'excluded_calibration_related_tasks': excluded,
        'available_unreserved_source_groups': {d: len(pool) for d, pool in pools.items()},
        'final_test_count': 0, 'untouched_final_claim': False,
        'native_variant_policy': 'one published native instance per base; no copies or generated padding',
        'original_target_base_tasks': 72, 'original_target_instances': 216,
        'original_t26_acceptance': 'blocked',
        'remaining': ['Three distinct original input variants per base are not supplied by these sources.',
                      'Untouched evaluator-side final corpus and separate evaluator principal required.'],
        'manifest_sha256': canonical_json_hash(selected)}
