"""Group identity before variant generation and keep final evaluation separate.

The private store is evaluator-side application storage. Deployment must also
exclude it from developer/candidate mounts and service accounts. A directory on
the same host is not an OS security boundary against that host's owner.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Literal, Callable

from pydantic import BaseModel, ConfigDict, Field

from .contracts import TaskSpec
from .hashing import canonical_json_hash, sha256_file
from .view_safety import checked_path, ordinary_file, relative_reference

SPLITS = ('develop', 'regression', 'promotion_validation', 'final_test', 'ood_transfer')
DOMAINS = ('excel', 'word', 'powerpoint')
TARGETS = dict(develop=8, regression=4, promotion_validation=4, final_test=4, ood_transfer=4)
Split = Literal['develop', 'regression', 'promotion_validation', 'final_test', 'ood_transfer']


class TaskFamilyManifest(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    base_task_id: str = Field(min_length=1)
    family_id: str = Field(min_length=1)
    source_document_id: str = Field(min_length=1)
    variant_ids: list[str] = Field(default_factory=list)
    domain: Literal['excel', 'word', 'powerpoint']
    split: Split | None = None
    source_hash: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    source_refs: list[str] = Field(default_factory=list)
    variant_input_hashes: dict[str, str] = Field(default_factory=dict)
    exposure: Literal['exposed', 'unexposed'] = 'exposed'


class FinalSeal(BaseModel):
    model_config = ConfigDict(extra='forbid')
    task_count: int = Field(ge=0)
    base_task_count: int = Field(ge=0)
    family_count: int = Field(ge=0)
    source_document_count: int = Field(ge=0)
    final_test_hash: str = Field(pattern=r'^[0-9a-f]{64}$')


def validate_family_splits(rows: list[TaskFamilyManifest]) -> None:
    seen_base, seen_variant = set(), set()
    owners = {key: {} for key in ('family_id', 'source_document_id', 'source_hash')}
    source_versions = {}
    for row in rows:
        if row.split is None:
            raise ValueError('every frozen family needs a split')
        if row.base_task_id in seen_base:
            raise ValueError('duplicate base task')
        seen_base.add(row.base_task_id)
        if row.split == 'final_test' and row.exposure != 'unexposed':
            raise ValueError('exposed content cannot be an untouched final_test')
        for key, mapping in owners.items():
            value = getattr(row, key)
            if value is not None:
                previous = mapping.setdefault(value, row.split)
                if previous != row.split:
                    raise ValueError(f'{key} overlap between splits')
        if row.source_hash is not None:
            previous = source_versions.setdefault(row.source_document_id, row.source_hash)
            if previous != row.source_hash:
                raise ValueError('source document identity maps to different hashes')
        for variant in row.variant_ids:
            if not variant or variant in seen_variant:
                raise ValueError('duplicate or empty variant identity')
            seen_variant.add(variant)
        if row.variant_input_hashes:
            if set(row.variant_input_hashes) != set(row.variant_ids):
                raise ValueError('variant input hash binding mismatch')
            for digest in row.variant_input_hashes.values():
                if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                    raise ValueError('invalid variant input hash')
                previous = owners['source_hash'].setdefault(digest, row.split)
                if previous != row.split:
                    raise ValueError('variant input hash overlap between splits')


def assign_grouped_splits(rows: list[TaskFamilyManifest], allocations: dict[str, dict[str, int]], *, seed: int) -> list[TaskFamilyManifest]:
    """Allocate whole connected groups, before any variants exist.

This deterministic allocator fails closed if a whole group cannot fit. It never
splits a family or pads the inventory with renamed copies.
"""
    if any(r.variant_ids or r.variant_input_hashes or r.split is not None for r in rows):
        raise ValueError('assign splits before variants or prior split assignment')
    if len({r.base_task_id for r in rows}) != len(rows):
        raise ValueError('duplicate base task')
    for domain, quotas in allocations.items():
        if domain not in DOMAINS or set(quotas) != set(SPLITS) or any(type(n) is not int or n < 0 for n in quotas.values()):
            raise ValueError('invalid allocation')
    remaining = sorted(rows, key=lambda r: r.base_task_id)
    groups = []
    while remaining:
        group = [remaining.pop(0)]
        changed = True
        while changed:
            changed = False
            for candidate in remaining[:]:
                if any(candidate.family_id == r.family_id or candidate.source_document_id == r.source_document_id
                       or (candidate.source_hash is not None and candidate.source_hash == r.source_hash) for r in group):
                    group.append(candidate)
                    remaining.remove(candidate)
                    changed = True
        if len({r.domain for r in group}) != 1:
            raise ValueError('a source/family allocation spans domains')
        groups.append(group)
    groups.sort(key=lambda g: (-len(g), canonical_json_hash([seed, sorted(r.base_task_id for r in g)])))
    capacity = {d: dict(q) for d, q in allocations.items()}
    result = []
    # Reserve unexposed groups for the final split before assigning exposed ones.
    groups.sort(key=lambda g: any(r.exposure == 'exposed' for r in g))
    for group in groups:
        choices = capacity.get(group[0].domain, {})
        allowed = [s for s in ('final_test', 'develop', 'regression', 'promotion_validation', 'ood_transfer')
                   if choices.get(s, 0) >= len(group) and (s != 'final_test' or all(r.exposure == 'unexposed' for r in group))]
        if not allowed:
            raise ValueError('insufficient independent families for whole-group allocation')
        split = allowed[0]
        choices[split] -= len(group)
        result.extend(r.model_copy(update={'split': split}) for r in group)
    if any(n != 0 for quotas in capacity.values() for n in quotas.values()):
        raise ValueError('insufficient independent families for requested allocation')
    result.sort(key=lambda r: r.base_task_id)
    validate_family_splits(result)
    return result


def split_quality_report(rows: list[TaskFamilyManifest]) -> dict:
    blockers = []
    try:
        validate_family_splits(rows)
    except ValueError as error:
        blockers.append(str(error))
    counts = {domain: dict(Counter(r.split or 'unassigned' for r in rows if r.domain == domain)) for domain in DOMAINS}
    if any(counts[d] != TARGETS for d in DOMAINS):
        blockers.append('Independent base tasks do not meet per-domain 8/4/4/4/4 targets.')
    if any(len(r.variant_ids) != 3 or len(set(r.variant_input_hashes.values())) != 3 for r in rows):
        blockers.append('Each base task needs three distinct, input-hashed variants.')
    if any(not r.source_refs or r.source_hash is None for r in rows):
        blockers.append('Source provenance and source-document hashes are required.')
    return {'schema_version': 'family-split-quality-v1', 'status': 'blocked' if blockers else 'pass',
            'scope': 'manifest integrity; file admission and deployment isolation remain separate',
            'target_base_tasks': 72, 'target_instances': 216,
            'actual_base_tasks': len(rows), 'actual_instances': sum(len(r.variant_ids) for r in rows),
            'family_count': len({r.family_id for r in rows}),
            'source_document_count': len({r.source_document_id for r in rows}),
            'per_domain_splits': counts, 'final_test_count': sum(len(r.variant_ids) for r in rows if r.split == 'final_test'),
            'blockers': blockers}


def developer_view(rows: list[TaskFamilyManifest], final_seal: dict) -> dict:
    validate_family_splits(rows)
    # Select fields rather than forwarding an arbitrary service response.
    final = {k: final_seal[k] for k in ('task_count', 'base_task_count', 'family_count', 'source_document_count', 'final_test_hash')}
    final = FinalSeal.model_validate(final).model_dump(mode='json')
    return {'develop': [r.model_dump(mode='json') for r in rows if r.split == 'develop'],
            'protected_splits': {s: {'base_task_count': sum(r.split == s for r in rows),
                'hash': canonical_json_hash([r.model_dump(mode='json') for r in rows if r.split == s])}
                for s in ('regression', 'promotion_validation', 'ood_transfer')}, 'final_test': final}


def prepare_adaptive_splits(tasks_by_split: dict, *, legacy_hidden_mapping: str | None = None) -> tuple[dict, dict]:
    if 'final_test' in tasks_by_split:
        raise ValueError('final_test cannot enter adaptive RSI; use the sealed evaluator separately')
    keys = set(tasks_by_split)
    modern = {'develop', 'regression', 'promotion_validation', 'ood_transfer'}
    if 'hidden' in keys:
        if legacy_hidden_mapping != 'promotion_validation':
            raise ValueError('legacy hidden requires explicit mapping to promotion_validation')
        expected = {'develop', 'regression', 'hidden', 'ood_transfer'}
        protected = 'hidden'
    else:
        if legacy_hidden_mapping is not None:
            raise ValueError('legacy hidden mapping supplied without a hidden split')
        expected, protected = modern, 'promotion_validation'
    if keys != expected or any(not tasks_by_split[s] for s in expected):
        raise ValueError('adaptive RSI needs nonempty develop, regression, promotion_validation and ood_transfer')
    result = {('hidden' if k == 'promotion_validation' else k): list(v) for k, v in tasks_by_split.items()}
    result['hidden'] = [t.model_copy(update={'hidden_test': True}) for t in result['hidden']]
    return result, {'schema_version': 'adaptive-split-role-v2',
        'legacy_hidden_maps_to': 'promotion_validation' if protected == 'hidden' else None,
        'internal_hidden_role': 'promotion_validation', 'untouched_final_test_claim': False,
        'final_test_used': False}


class SealedFinalStore:
    """Evaluator-only snapshots with hash verification and one-use evaluation."""
    def __init__(self, private_root: str | Path, *, developer_roots: list[Path]):
        self.root = checked_path(private_root).resolve()
        if not developer_roots:
            raise ValueError('developer roots must be declared')
        for root in developer_roots:
            root = checked_path(root).resolve()
            if self.root.is_relative_to(root) or root.is_relative_to(self.root):
                raise ValueError('final store must be outside developer roots')

    def seal(self, families: list[TaskFamilyManifest], tasks: dict[str, dict], *, input_files: dict[str, Path] | None = None) -> dict:
        validate_family_splits(families)
        if not families or any(r.split != 'final_test' or not r.variant_ids for r in families):
            raise ValueError('seal needs nonempty final_test families')
        ids = {v for r in families for v in r.variant_ids}
        if ids != set(tasks):
            raise ValueError('final task binding mismatch')
        domains = {v: r.domain for r in families for v in r.variant_ids}
        admitted = {}
        for name, task in tasks.items():
            parsed = TaskSpec.model_validate(task)
            if parsed.task_id != name or parsed.domain != domains[name]:
                raise ValueError('final task identity/domain binding mismatch')
            admitted[name] = parsed
        sources = input_files or {}
        if {f for t in admitted.values() for f in t.input_files} != set(sources):
            raise ValueError('final input binding mismatch')
        frozen = {}
        for name, path in sources.items():
            relative_reference(name)
            frozen[name] = ordinary_file(path).read_bytes()
        if self.root.exists():
            raise FileExistsError(self.root)
        self.root.mkdir(parents=True)
        (self.root / 'inputs').mkdir()
        input_hashes = {}
        from .hashing import sha256_bytes
        for name, body in frozen.items():
            digest = sha256_bytes(body)
            target = f'inputs/{digest}'
            (self.root / target).write_bytes(body)
            input_hashes[name] = {'path': target, 'sha256': digest}
        payload = {'families': [r.model_dump(mode='json') for r in families],
                   'tasks': {k: t.model_dump(mode='json') for k, t in admitted.items()}, 'inputs': input_hashes}
        self._write('sealed-final.json', payload)
        digest = self.verify()
        return {'task_count': len(tasks), 'base_task_count': len(families),
                'family_count': len({r.family_id for r in families}),
                'source_document_count': len({r.source_document_id for r in families}), 'final_test_hash': digest}

    def verify(self) -> str:
        path = ordinary_file(self.root / 'sealed-final.json')
        payload = json.loads(path.read_text(encoding='utf-8'))
        for entry in payload['inputs'].values():
            relative_reference(entry['path'])
            source = ordinary_file(self.root / entry['path'])
            if sha256_file(source) != entry['sha256']:
                raise ValueError('sealed final input hash mismatch')
        return sha256_file(path)

    def evaluate_once(self, expected_hash: str, evaluator: Callable[[list[TaskSpec]], dict]) -> dict:
        if self.verify() != expected_hash:
            raise ValueError('sealed final manifest hash mismatch')
        # Exclusive marker is written before the callback: failures do not grant a retry.
        with (self.root / 'consumed.json').open('x', encoding='utf-8') as handle:
            json.dump({'final_test_hash': expected_hash}, handle)
        payload = json.loads((self.root / 'sealed-final.json').read_text(encoding='utf-8'))
        tasks = []
        for entry in payload['tasks'].values():
            task = TaskSpec.model_validate(entry)
            tasks.append(task.model_copy(update={'input_files': tuple(str(self.root / payload['inputs'][f]['path']) for f in task.input_files), 'hidden_test': True}))
        result = evaluator(tasks)
        if self.verify() != expected_hash:
            raise ValueError('sealed final content hash changed during evaluation')
        self._write('evaluation-result.json', result)
        return {'task_count': len(tasks), 'result_hash': sha256_file(self.root / 'evaluation-result.json')}

    def _write(self, name: str, payload: dict):
        with (self.root / name).open('x', encoding='utf-8') as handle:
            handle.write(json.dumps(payload, sort_keys=True, indent=2) + '\n')
