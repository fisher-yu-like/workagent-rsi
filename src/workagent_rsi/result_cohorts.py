"""Read-only comparable result cohorts and exclusive paired reference runs."""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import shutil
from typing import Literal

from pydantic import Field

from .candidate_normalization import parse_candidate_json
from .hashing import canonical_json_hash, sha256_file
from .run_contracts import RunContract
from .view_safety import checked_path, ordinary_file, relative_reference


class CohortKey(RunContract):
    mode: Literal['pilot', 'formal']
    dataset_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    split_hashes_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    evaluator_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    acceptance_hashes_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    model_config_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    experiment_arm: str = Field(min_length=1)
    budget_policy_hash: str = Field(pattern=r'^[0-9a-f]{64}$')


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('missing or invalid SHA-256 identity')
    return value


def _file_ref(base, ref):
    if not isinstance(ref, dict) or set(ref) != {'path', 'sha256'}:
        raise ValueError('missing verifiable file reference')
    relative = relative_reference(ref['path'])
    path = ordinary_file(Path(base)/Path(*relative.parts))
    if path.stat().st_size > 16777216:
        raise ValueError('analysis evidence file exceeds 16 MiB read budget')
    if sha256_file(path) != _sha(ref['sha256']):
        raise ValueError('evidence file SHA-256 mismatch')
    return path


def _json_ref(base, ref):
    path = _file_ref(base, ref)
    value = parse_candidate_json(path.read_text(encoding='utf-8'))
    if sha256_file(path) != ref['sha256']:
        raise ValueError('evidence changed during analysis')
    return value


def _metrics(value, *, empty=False):
    if not isinstance(value, dict) or (not value and not empty):
        raise ValueError('missing numeric metrics')
    result = {}
    for name, number in value.items():
        if (not isinstance(name, str) or not name or type(number) not in {int, float}
                or not math.isfinite(number)):
            raise ValueError('metric must be finite numeric data, never bool/NaN/Infinity')
        result[name] = float(number)
    return result


def _mean(numbers):
    try:
        value = math.fsum(number/len(numbers) for number in numbers)
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError('invalid numeric aggregation') from exc
    if not math.isfinite(value):
        raise ValueError('non-finite aggregate')
    return value


def _identity(value, mode):
    required = {'schema_version', 'mode', 'dataset_hash', 'split_hashes', 'evaluator_hash',
                'acceptance_hashes', 'model_config', 'experiment_arm', 'budget_policy'}
    if not isinstance(value, dict) or set(value) != required or value['schema_version'] != 'cohort-identity-v1':
        raise ValueError('missing registered cohort identity')
    if value['mode'] != mode:
        raise ValueError('summary/identity mode mismatch')
    for name in ['split_hashes', 'acceptance_hashes']:
        if not isinstance(value[name], dict) or not value[name]:
            raise ValueError('missing identity map: ' + name)
        for key, digest in value[name].items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError('empty identity-map key')
            _sha(digest)
    if value['dataset_hash'] != canonical_json_hash(value['split_hashes']):
        raise ValueError('dataset hash does not bind the declared splits')
    for name in ['model_config', 'budget_policy']:
        if not isinstance(value[name], dict) or not value[name]:
            raise ValueError('missing comparable configuration: ' + name)
        json.dumps(value[name], allow_nan=False)
    model = value['model_config']
    if (not isinstance(model.get('provider'), str) or not model['provider'].strip() or 'model' not in model
            or (model['model'] is not None and not isinstance(model['model'], str))
            or str(model['model']).lower() in {'unknown', 'unavailable', 'not_probed', ''}):
        raise ValueError('unknown model configuration identity')
    if not isinstance(value['experiment_arm'], str) or not value['experiment_arm'].strip():
        raise ValueError('unknown experiment arm identity')
    if model['model'] is None and model['provider'] not in {'deterministic', 'local-office', 'authored-fixture'}:
        raise ValueError('null model identity is allowed only for explicit non-model providers')
    return CohortKey(mode=mode, dataset_hash=value['dataset_hash'],
        split_hashes_hash=canonical_json_hash(value['split_hashes']), evaluator_hash=value['evaluator_hash'],
        acceptance_hashes_hash=canonical_json_hash(value['acceptance_hashes']),
        model_config_hash=canonical_json_hash(model), experiment_arm=value['experiment_arm'],
        budget_policy_hash=canonical_json_hash(value['budget_policy']))


def _admission(base, entry, identity, summary):
    """A boolean receipt is insufficient: verify bound source/quality/data bytes."""
    if identity['mode'] != 'formal':
        return False, 'pilot cohort cannot authorize external claims'
    try:
        boundary = summary.get('claim_boundary')
        if (summary.get('dataset_kind') != 'external-admitted' or not isinstance(boundary, dict)
                or boundary.get('external_benchmark') is not True):
            raise ValueError('formal source/claim boundary not admitted')
        proof = _json_ref(base, entry.get('admission_ref'))
        if (not isinstance(proof, dict) or proof.get('schema_version') != 'cohort-admission-v1' or proof.get('ready') is not True
                or proof.get('identity_hash') != canonical_json_hash(identity)
                or proof.get('dataset_hash') != identity['dataset_hash']):
            raise ValueError('admission proof does not bind this cohort identity')
        source = _json_ref(base, proof.get('source_manifest'))
        quality = _json_ref(base, proof.get('quality_report'))
        if not isinstance(source, dict) or not isinstance(quality, dict):
            raise ValueError('source/quality proof must be an object')
        selected = source.get('formal_dataset_selected')
        listed = source.get('candidates', [])
        if not isinstance(listed, list) or any(not isinstance(c, dict) for c in listed):
            raise ValueError('invalid source candidate list')
        candidates = [c for c in listed if c.get('id') == selected]
        if (source.get('status') != 'ready' or not isinstance(selected, str)
                or not selected.strip() or len(candidates) != 1):
            raise ValueError('source admission is incomplete')
        candidate = candidates[0]
        if (candidate.get('license_status') != 'verified' or not isinstance(candidate.get('data_license'), str)
                or not candidate['data_license'].strip()
                or candidate.get('download_status') not in {'admitted', 'downloaded'}):
            raise ValueError('source license/download admission failed')
        _sha(candidate.get('checksum'))
        if quality.get('status') != 'pass' or quality.get('formal_dataset_selected') != selected:
            raise ValueError('source quality admission failed')
        refs = proof.get('splits', {})
        if set(refs) != set(identity['split_hashes']):
            raise ValueError('admission split coverage differs from cohort')
        task_ids = []
        for split, ref in refs.items():
            path = _file_ref(base, ref)
            rows = [parse_candidate_json(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
            if sha256_file(path) != ref['sha256']:
                raise ValueError('admitted data changed during analysis')
            if canonical_json_hash(rows) != identity['split_hashes'][split]:
                raise ValueError('admitted split hash mismatch')
            if any(not isinstance(row, dict) or not isinstance(row.get('task_id'), str) for row in rows):
                raise ValueError('admitted task identity missing')
            task_ids.extend(row['task_id'] for row in rows)
        if len(set(task_ids)) != len(task_ids) or set(task_ids) != set(identity['acceptance_hashes']):
            raise ValueError('admitted task coverage incomplete or overlapping')
        return True, None
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return False, str(exc)


def _verified(record):
    summary, entry, path = record['summary'], record['entry'], record['path']
    base = path.parent
    identity = _json_ref(base, entry.get('identity_ref'))
    key = _identity(identity, summary['mode'])
    result = _json_ref(base, entry.get('result_ref'))
    if (not isinstance(result, dict) or result.get('run_id') != entry['run_id']
            or type(result.get('attempt_id')) is not int or result.get('attempt_id') != entry['attempt_id']
            or result.get('status') != entry.get('status')
            or result.get('identity_hash') != canonical_json_hash(identity)):
        raise ValueError('result is not bound to this run/attempt/identity/status')
    evidence_id = _sha(result.get('evidence_id'))
    metrics = _metrics(result.get('metrics'), empty=entry.get('status') != 'completed')
    if metrics != _metrics(entry.get('metrics'), empty=entry.get('status') != 'completed'):
        raise ValueError('summary metrics differ from bound result')
    rows = result.get('task_results', [])
    if entry.get('status') == 'completed':
        if (not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
                or len(rows) != len(identity['acceptance_hashes'])
                or {row.get('task_id') for row in rows} != set(identity['acceptance_hashes'])):
            raise ValueError('completed result task coverage incomplete or duplicate')
        checked = [_metrics(row.get('metrics')) for row in rows]
        if any(set(row) != set(metrics) for row in checked):
            raise ValueError('per-task metric coverage incomplete')
        if any(not math.isclose(metrics[name], _mean([row[name] for row in checked]), rel_tol=1e-12, abs_tol=1e-12)
               for name in metrics):
            raise ValueError('run metric does not match task observations')
    admitted, reason = _admission(base, entry, identity, summary)
    return {**record, 'key': key, 'identity': identity, 'metrics': metrics, 'rows': rows,
            'evidence_id': evidence_id, 'claims_allowed': admitted, 'claim_reason': reason}


def analyze_cohorts(root: Path) -> dict:
    root = checked_path(root)
    if not root.is_dir():
        raise ValueError('analysis root must be a directory')
    excluded, records, observed = [], [], Counter()
    source_count = 0
    def exclude(record, reason):
        excluded.append({'source': record.get('source'), 'run_id': record.get('entry', {}).get('run_id'),
                         'attempt_id': record.get('entry', {}).get('attempt_id'), 'reason': reason})
    def traversal_error(error):
        exclude({'source': str(error.filename)}, 'unreadable analysis directory')
    for directory, folders, files in os.walk(root, followlinks=False, onerror=traversal_error):
        safe = []
        for folder in folders:
            try:
                checked_path(Path(directory)/folder)
                safe.append(folder)
            except ValueError:
                exclude({'source': (Path(directory)/folder).relative_to(root).as_posix()}, 'linked analysis directory excluded')
        folders[:] = sorted(safe)
        if 'summary.json' not in files:
            continue
        path = Path(directory)/'summary.json'
        source = path.relative_to(root).as_posix()
        try:
            if ordinary_file(path).stat().st_size > 16777216:
                raise ValueError('summary exceeds analysis read budget')
            summary = parse_candidate_json(ordinary_file(path).read_text(encoding='utf-8'))
            if not isinstance(summary, dict) or summary.get('mode') not in {'pilot', 'formal'} or not isinstance(summary.get('experiments'), list):
                continue
            source_count += 1
            for entry in summary['experiments']:
                if not isinstance(entry, dict):
                    exclude({'source': source}, 'invalid experiment entry')
                    continue
                observed[str(entry.get('status'))] += 1
                record = {'summary': summary, 'entry': entry, 'path': path, 'source': source}
                if (not isinstance(entry.get('run_id'), str) or not entry['run_id'].strip()
                        or type(entry.get('attempt_id')) is not int or entry['attempt_id'] < 1):
                    exclude(record, 'missing run_id/positive attempt_id; legacy identity is not inferred')
                else:
                    records.append(record)
        except (ValueError, OSError, TypeError) as exc:
            exclude({'source': source}, 'invalid summary: ' + str(exc))
    by_run = defaultdict(list)
    for record in records:
        by_run[record['entry']['run_id']].append(record)
    selected = []
    for run_id, attempts in sorted(by_run.items()):
        latest = max(record['entry']['attempt_id'] for record in attempts)
        current = [r for r in attempts if r['entry']['attempt_id'] == latest]
        older = [r for r in attempts if r['entry']['attempt_id'] != latest]
        for record in older:
            exclude(record, 'superseded_attempt')
        fingerprints = {canonical_json_hash({'mode':r['summary']['mode'], 'entry':r['entry'],
                         'dataset_kind':r['summary'].get('dataset_kind'), 'claim_boundary':r['summary'].get('claim_boundary')}) for r in current}
        if len(fingerprints) != 1:
            for record in current:
                exclude(record, 'conflicting_duplicate_attempt')
            continue
        current.sort(key=lambda r: r['source'])
        for record in current[1:]:
            exclude(record, 'duplicate_attempt')
        record = current[0]
        try:
            verified = _verified(record)
            for previous in older:
                try:
                    previous_key = _verified(previous)['key']
                except (ValueError, OSError, TypeError, KeyError):
                    continue
                if previous_key != verified['key']:
                    raise ValueError('retry changed comparable experiment identity')
            if record['entry'].get('status') != 'completed':
                raise ValueError('latest attempt is not completed; no fallback to older success')
            selected.append(verified)
        except (ValueError, OSError, TypeError, KeyError, OverflowError) as exc:
            exclude(record, str(exc))
    evidence_counts = Counter(record['evidence_id'] for record in selected)
    grouped = defaultdict(list)
    for record in selected:
        if evidence_counts[record['evidence_id']] > 1:
            exclude(record, 'reused evidence across logical runs')
        else:
            grouped[record['key']].append(record)
    cohorts = []
    for key, group in sorted(grouped.items(), key=lambda pair: canonical_json_hash(pair[0].model_dump())):
        metric_values = defaultdict(list)
        observations = []
        for record in group:
            for name, value in record['metrics'].items():
                metric_values[name].append(value)
            observations.append({'run_id':record['entry']['run_id'], 'attempt_id':record['entry']['attempt_id'],
                'source':record['source'], 'result_ref':record['entry']['result_ref'], 'identity_ref':record['entry']['identity_ref'],
                'evidence_id':record['evidence_id'], 'metrics':record['metrics'], 'task_count':len(record['rows']),
                'claims_allowed':record['claims_allowed'], 'claim_reason':record['claim_reason']})
        equal_metrics = len({tuple(sorted(record['metrics'])) for record in group}) == 1
        try:
            means = {name:_mean(values) for name,values in sorted(metric_values.items())}
        except ValueError as exc:
            for record in group:
                exclude(record, 'invalid aggregate: ' + str(exc))
            continue
        cohorts.append({'cohort_id':canonical_json_hash(key.model_dump()), 'key':key.model_dump(mode='json'),
            'sample_count':len(group), 'task_observation_count':sum(len(record['rows']) for record in group),
            'numeric_means':means,
            'metric_denominators':{name:len(values) for name,values in sorted(metric_values.items())},
            'claims_allowed':key.mode == 'formal' and equal_metrics and all(record['claims_allowed'] for record in group),
            'observations':observations})
    blocking = [r for r in excluded if r['reason'] not in {'superseded_attempt', 'duplicate_attempt'}]
    one = len(cohorts) == 1 and not blocking
    return {'schema_version':'cohort-analysis-v1', 'results_root':str(root), 'source_summary_count':source_count,
        'completed_experiments':sum(c['sample_count'] for c in cohorts),
        'unavailable_experiments':observed['unavailable']+observed['timeout'],
        'failed_experiments':sum(n for status,n in observed.items() if status not in {'completed','unavailable','timeout'}),
        'observed_status_counts':dict(observed), 'cohorts':cohorts, 'excluded_records':excluded,
        'numeric_means':cohorts[0]['numeric_means'] if one else {},
        'claims_allowed':one and cohorts[0]['claims_allowed'],
        'retry_policy':'highest declared attempt; no fallback; conflicting duplicates excluded',
        'claim_boundary':{'unavailable_is_not_a_score':True,'pilot_is_not_external_benchmark':True,
                          'claims_are_cohort_scoped':True,'unknown_identity_is_not_aggregated':True}}


def paired_reference_evaluation(destination, *, tasks, parent_package, candidate_package,
                                evaluator, evaluator_hash, source_runs=None):
    """Re-evaluate both versions on identical tasks into a new exclusive run."""
    root = checked_path(destination)
    _sha(evaluator_hash)
    if root.exists():
        raise FileExistsError(root)
    if (not tasks or any(not isinstance(t, dict) or not isinstance(t.get('task_id'), str)
                         or not t['task_id'].strip() for t in tasks)
            or len({t['task_id'] for t in tasks}) != len(tasks)):
        raise ValueError('reference tasks must have unique explicit task IDs')
    root.mkdir(parents=True)
    record = {'kind':'reference_eval_run','status':'running','started_at':datetime.now(timezone.utc).isoformat(),
        'evaluator_hash':evaluator_hash,'taskset_hash':canonical_json_hash(tasks),
        'parent_package_hash':canonical_json_hash(parent_package),'candidate_package_hash':canonical_json_hash(candidate_package),
        'source_runs':{},'task_count':len(tasks),'rows':[],'claims_allowed':False}
    try:
        inputs = root/'inputs.json'
        inputs.write_text(json.dumps({'tasks':tasks,'parent_package':parent_package,'candidate_package':candidate_package},
                                    indent=2,allow_nan=False)+'\n',encoding='utf-8')
        record['inputs']={'path':'inputs.json','sha256':sha256_file(inputs)}
        for name, source in (source_runs or {}).items():
            relative = relative_reference(name)
            path = ordinary_file(source)
            digest = sha256_file(path)
            target = root/'source'/Path(*relative.parts)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,target)
            if sha256_file(path) != digest or sha256_file(target) != digest:
                raise ValueError('historical source changed during reference copy')
            record['source_runs'][name]={'path':target.relative_to(root).as_posix(),'sha256':digest}
        metric_names = None
        for task in tasks:
            parent = _metrics(evaluator(deepcopy(task),deepcopy(parent_package)))
            candidate = _metrics(evaluator(deepcopy(task),deepcopy(candidate_package)))
            if set(parent) != set(candidate) or (metric_names is not None and set(parent) != metric_names):
                raise ValueError('paired reference metric coverage differs')
            metric_names = set(parent)
            delta = _metrics({name:candidate[name]-parent[name] for name in parent})
            record['rows'].append({'task_id':task['task_id'],'parent':parent,'candidate':candidate,'delta':delta})
        record['paired_deltas']={name:_mean([row['delta'][name] for row in record['rows']]) for name in sorted(metric_names)}
        record['status']='completed'
    except Exception as exc:
        record.update(status='failed',error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        record['ended_at']=datetime.now(timezone.utc).isoformat()
        (root/'reference_eval_run.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return record
