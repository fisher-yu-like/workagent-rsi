"""Whole-response candidate admission and deterministic, auditable conversion."""
from __future__ import annotations

from datetime import datetime
import json

from .candidate_context import CandidateContext
from .hashing import canonical_json_hash
from .rsi_contracts import AtomicEdit, CandidatePatch, CandidateNormalizationRecord


def parse_candidate_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate candidate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError('non-finite candidate JSON constant: ' + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(field + ' must be a nonempty string')
    return value  # Whitespace and all instruction characters are preserved.


def _time(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError('created_at must be an actual timestamp with timezone')
    return value


def normalize_candidate(raw: dict, context: CandidateContext, *, provider_metadata=None,
                        normalization_record=None) -> CandidatePatch:
    """Accept registered envelopes only; never delete edits to rescue a response.

    provider_metadata is supplied by the trusted transport, not read from raw.
    Without it, identity is explicitly unobserved and cannot acquire a model
    name from response self-report. Hypotheses/metrics must always be supplied.
    """
    context = CandidateContext.model_validate(context.model_dump())
    audit = {'status': 'rejected', 'context_hash': context.fingerprint(), 'raw_sha256': None,
             'mappings': [], 'metadata_provenance': {}}
    provenance, mappings = audit['metadata_provenance'], audit['mappings']
    try:
        # Reject direct Python inputs that cannot be faithfully represented as JSON.
        json.dumps(raw, allow_nan=False)
        audit['raw_sha256'] = canonical_json_hash(raw)
        if not isinstance(raw, dict):
            raise ValueError('candidate response must be an object')
        version = raw.get('schema_version')
        if version is None and 'schema_version' not in raw:
            envelope, edit_key = 'canonical-v1', 'atomic_edits'
        elif version == 'candidate-patch-v1':
            envelope, edit_key = version, 'edits'
        else:
            raise ValueError('unsupported candidate patch envelope version')
        audit['envelope'] = envelope
        common = {'candidate_id', 'parent_version', 'provider', 'provider_version', 'model_identity',
                  'diagnosis_refs', 'new_tests', 'edit_budget', 'created_at'}
        allowed = common | {edit_key} | ({'schema_version'} if version else set())
        if set(raw) - allowed:
            raise ValueError('unknown candidate response fields: ' + ', '.join(sorted(set(raw)-allowed)))
        edits = raw.get(edit_key)
        if not isinstance(edits, list) or not edits:
            raise ValueError('candidate edits must be a nonempty list')
        if len(edits) > context.edit_budget:
            raise ValueError(f'candidate edit budget exceeded: {len(edits)} > {context.edit_budget}; whole response rejected')
        if 'edit_budget' in raw and (type(raw['edit_budget']) is not int or raw['edit_budget'] != context.edit_budget):
            raise ValueError('raw edit_budget must equal the trusted context budget')
        if raw.get('parent_version', context.parent_version) != context.parent_version:
            raise ValueError('candidate parent_version differs from trusted context')
        for name in ['candidate_id', 'parent_version', 'provider', 'provider_version']:
            if name in raw:
                _text(raw[name], name)
        if 'model_identity' in raw and raw['model_identity'] is not None:
            _text(raw['model_identity'], 'model_identity')

        editable = ({'instructions'} if 'instructions' in context.champion_package else
                    {'marker_source', 'sales_rows', 'sales_chart', 'sales_number_format'} & context.champion_package.keys())
        admitted, seen = [], set()
        for index, item in enumerate(edits):
            if not isinstance(item, dict):
                raise ValueError('every candidate edit must be an object')
            if edit_key == 'atomic_edits':
                if set(item) - {'component', 'target_path', 'patch', 'hypothesis', 'expected_metric'}:
                    raise ValueError('unknown atomic edit field')
                target = item.get('target_path')
                patch_value = item.get('patch')
                if isinstance(patch_value, str):
                    patch_value = parse_candidate_json(patch_value)
                    transform = 'parse JSON patch string; preserve field value'
                else:
                    transform = 'serialize one-key patch object; preserve field value'
            else:
                if set(item) - {'file', 'target', 'value', 'hypothesis', 'expected_metric'}:
                    raise ValueError('unknown registered edit field')
                target = item.get('file')
                field = _text(item.get('target'), 'edit target')
                if 'value' not in item:
                    raise ValueError('edit value is required')
                patch_value = {field: item['value']}
                transform = 'map registered target/value to one-key patch'
            if target != 'skill.json':
                raise ValueError('candidate edit must target skill.json')
            if not isinstance(patch_value, dict) or len(patch_value) != 1:
                raise ValueError('candidate patch must contain exactly one field')
            field, value = next(iter(patch_value.items()))
            if field not in editable:
                raise ValueError('candidate field is forbidden or absent from champion: ' + str(field))
            if field in seen:
                raise ValueError('duplicate or overlapping candidate field: ' + field)
            seen.add(field)
            if type(value) is not type(context.champion_package[field]):
                raise ValueError('candidate field type differs from champion: ' + field)
            if isinstance(value, str):
                _text(value, field)
            hypothesis = _text(item.get('hypothesis'), 'hypothesis (required from model)')
            metric = _text(item.get('expected_metric'), 'expected_metric (required from model)')
            component = item.get('component', 'prompt' if field in {'instructions', 'marker_source'} else 'tool_policy')
            if component not in {'prompt', 'tool_policy'} or (field == 'instructions' and component != 'prompt'):
                raise ValueError('candidate component is not permitted for this skill field')
            admitted.append((index, field, patch_value, component, hypothesis, metric, transform))
            if 'component' not in item:
                provenance[f'atomic_edits[{index}].component'] = 'registered envelope mapping'

        if 'diagnosis_refs' in raw:
            refs = raw['diagnosis_refs']
            if isinstance(refs, list):
                converted = []
                for index, ref in enumerate(refs):
                    if isinstance(ref, dict) and set(ref) == {'ref'}:
                        mappings.append({'source': f'diagnosis_refs[{index}].ref',
                                         'target': f'diagnosis_refs[{index}]', 'transform': 'registered reference wrapper'})
                        ref = ref['ref']
                    converted.append(ref)
                refs = converted
            provenance['diagnosis_refs'] = 'raw.diagnosis_refs'
        elif context.diagnoses:
            refs = [ref for diagnosis in context.diagnoses for ref in diagnosis.evidence_refs]
            provenance['diagnosis_refs'] = 'context.diagnoses'
        elif context.develop_feedback.tasks:
            refs = [canonical_json_hash(context.develop_feedback.model_dump(mode='json'))]
            provenance['diagnosis_refs'] = 'context.develop_feedback'
        else:
            raise ValueError('diagnosis_refs missing and no actual develop feedback source exists')
        if not isinstance(refs, list) or not refs or any(not isinstance(r, str) or not r.strip() for r in refs):
            raise ValueError('diagnosis_refs must contain nonempty source references')
        new_tests = raw.get('new_tests', [])
        if not isinstance(new_tests, list) or any(not isinstance(t, str) or not t.strip() for t in new_tests):
            raise ValueError('new_tests must be a list of nonempty strings')
        metadata = provider_metadata or {}
        if set(metadata) - {'provider', 'provider_version', 'model_identity', 'created_at'}:
            raise ValueError('unknown trusted provider metadata field')
        provider = _text(metadata.get('provider', 'unobserved-transport'), 'observed provider')
        provider_version = _text(metadata.get('provider_version', 'unobserved'), 'observed provider_version')
        model = metadata.get('model_identity')
        if model is not None:
            _text(model, 'observed model_identity')
        for field in ['provider', 'provider_version', 'model_identity']:
            provenance[field] = 'provider_metadata' if field in metadata else 'unobserved transport identity'
        if 'created_at' in raw:
            created = _time(raw['created_at'])
            provenance['created_at'] = 'raw.created_at'
        elif 'created_at' in metadata:
            created = _time(metadata['created_at'])
            provenance['created_at'] = 'provider_metadata'
        else:
            raise ValueError('created_at missing and no observed provider timestamp exists')
        identity = raw.get('candidate_id', canonical_json_hash({'raw': audit['raw_sha256'], 'context': context.fingerprint()})[:20])
        for field in ['parent_version', 'edit_budget']:
            provenance[field] = f'raw.{field} verified against context' if field in raw else f'context.{field}'
        provenance['candidate_id'] = 'raw.candidate_id' if 'candidate_id' in raw else 'deterministic raw/context hash'
        provenance['new_tests'] = 'raw.new_tests' if 'new_tests' in raw else 'contract default: empty'
        # Admission of the complete edit list AND raw metadata finishes before
        # constructing any normalized edit. No accepted prefix can escape.
        normalized = []
        for index, field, patch_value, component, hypothesis, metric, transform in admitted:
            normalized.append(AtomicEdit(component=component, target_path='skill.json', hypothesis=hypothesis,
                                         expected_metric=metric, patch=json.dumps(patch_value, ensure_ascii=False)))
            mappings.append({'source': f'{edit_key}[{index}]', 'target': f'atomic_edits[{index}].patch.{field}',
                             'transform': transform})
        patch = CandidatePatch(candidate_id=identity, parent_version=context.parent_version,
            provider=provider, provider_version=provider_version, model_identity=model,
            diagnosis_refs=refs, atomic_edits=normalized, new_tests=new_tests,
            edit_budget=context.edit_budget, created_at=created)
        audit.update(status='accepted', normalized_sha256=canonical_json_hash(patch.model_dump(mode='json')))
        return patch
    except (ValueError, TypeError, KeyError) as exc:
        audit['error'] = str(exc)
        raise ValueError('candidate normalization rejected: ' + str(exc)) from exc
    finally:
        if normalization_record is not None:
            normalization_record.clear()
            normalization_record.update(CandidateNormalizationRecord.model_validate(audit).model_dump(mode='json'))
