"""Interleaved, uncached paired execution and family-level comparison.

This controller can gate engineering promotion. Research qualification is a
separate release claim requiring human calibration and admitted held-out data.
"""
from dataclasses import asdict, replace
import json
from pathlib import Path
from statistics import pvariance

from .hashing import canonical_json_hash, sha256_file
from .statistical_promotion import ComparisonPolicy, RepeatedObservation, compare_repeated_runs


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _observation(row, task, repeat, contract):
    directory = Path(row.get('result_dir', ''))
    log = directory / 'provider_records' / 'tool_events.jsonl'
    verified = False
    evidence = []
    if log.is_file():
        try:
            events = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]
            for event in events:
                result = event.get('result', {})
                digest = result.get('script_sha256')
                reference = result.get('script_snapshot_ref')
                if event.get('name') != 'run_python' or not isinstance(digest, str):
                    continue
                if len(digest) != 64 or reference != 'executed-scripts/' + digest + '.py':
                    continue
                script = directory / 'provider_records' / reference
                if script.is_file() and sha256_file(script) == digest:
                    evidence.append(digest)
            verified = bool(evidence)
        except (OSError, ValueError, UnicodeError):
            pass
    telemetry = [item for channel in ('semantic', 'visual')
                 for item in row.get('telemetry', {}).get(channel, [])]
    independent = all(item.get('model_calls', 0) > 0 for item in telemetry)
    identity = canonical_json_hash({'directory': str(directory.resolve()), 'scripts': evidence,
                                    'log': sha256_file(log) if log.is_file() else None})
    return RepeatedObservation(task_id=task.task_id,
        family_id=contract.task_families[task.task_id], domain=task.domain, repeat=repeat,
        execution_id=identity, execution_valid=verified and row.get('task_outcome_complete') is True,
        execution_succeeded=row.get('execution_success') is True,
        task_succeeded=row.get('task_success') is True,
        quality_score=row.get('quality_score'),
        quality_comparable=row.get('assessment_complete') is True and independent,
        judge_observation_id=canonical_json_hash({'execution':identity, 'assessment':row.get('score_report')}),
        protocol_hash=canonical_json_hash({'contract':contract.model_dump(mode='json')}),
        unsafe_actions=int((row.get('execution_outcome') or {}).get('failure_origin') == 'safety'))


def _merge(reports, expected_repeats):
    merged = dict(reports[0])
    rows = []
    for index, first in enumerate(reports[0]['rows']):
        repeats = [report['rows'][index]['repeats'][0] for report in reports]
        if any(r['task_id'] != first['task_id'] for r in repeats):
            raise ValueError('repeat task order changed')
        representative = next((r for r in repeats if not r.get('task_outcome_complete')), None)
        representative = representative or next((r for r in repeats if not r.get('task_success')), repeats[0])
        rows.append({**representative, 'repeat_count':len(repeats), 'repeats':repeats})
    flat = [r for row in rows for r in row['repeats']]
    complete = len(reports) == expected_repeats and all(r.get('assessment_complete') for r in flat)
    outcomes = len(reports) == expected_repeats and all(r.get('task_outcome_complete') for r in flat)
    merged.update(rows=rows, assessment_complete=complete, task_outcomes_complete=outcomes,
        execution_complete=all(r.get('execution_complete') for r in flat),
        evaluation_seconds=sum(r.get('evaluation_seconds', 0) for r in reports),
        quality_score=sum(r['quality_score'] for r in flat)/len(flat) if complete else None,
        repeat_agreement=all(len({(r.get('task_success'), r.get('quality_score')) for r in row['repeats']}) == 1 for row in rows),
        task_success_rate=sum(r.get('task_success') is True for r in rows)/len(rows) if outcomes else None,
        execution_success_rate=sum(r.get('execution_success') is True for r in rows)/len(rows) if outcomes else None,
        quality_denominator=sum(r.get('assessment_complete') is True for r in rows),
        repeated_observation_count=len(flat), expected_observation_count=len(rows)*expected_repeats,
        repeated_task_success_rate=sum(r.get('task_success') is True for r in flat)/len(flat) if outcomes else None,
        repeated_execution_success_rate=sum(r.get('execution_success') is True for r in flat)/len(flat) if outcomes else None,
        execution_variance=pvariance(float(r.get('execution_success') is True) for r in flat),
        quality_variance=pvariance(r['quality_score'] for r in flat) if complete else None,
        judge_variance=None, judge_variance_status='not_identified_without_same_artifact_rejudgement')
    merged['score'] = merged['quality_score']
    merged['success_rate'] = merged['task_success_rate']
    return merged


def evaluate_paired(evaluator, tasks_by_split, baseline_config, candidate_config, contract, root):
    policy = ComparisonPolicy(**contract.comparison_policy)
    tasks = [t for batch in tasks_by_split.values() for t in batch]
    if contract.repeats != policy.required_repeats or set(contract.task_families) != {t.task_id for t in tasks}:
        raise ValueError('paired execution requires frozen family identities and exact repeat count')
    if set(tasks_by_split) != {'develop', 'regression', 'hidden', 'ood_transfer'}:
        raise ValueError('paired execution requires all four adaptive splits')
    if any({t.domain for t in batch} != {'excel', 'word', 'powerpoint'} for batch in tasks_by_split.values()):
        raise ValueError('each comparison split requires all three domains')
    root = Path(root)
    schedule = []
    collected = {side:{split:[] for split in tasks_by_split} for side in ('baseline','candidate')}
    observations = {side:{split:[] for split in tasks_by_split} for side in collected}
    single = contract.model_copy(update={'repeats':1})
    for repeat in range(policy.required_repeats):
        for side in (('baseline','candidate') if repeat % 2 == 0 else ('candidate','baseline')):
            for split, batch in tasks_by_split.items():
                directory = root/'paired-attempts'/f'repeat-{repeat+1}'/side/split
                if directory.exists():
                    raise FileExistsError('paired attempts are immutable; resume creates a new round attempt')
                schedule.append({'repeat':repeat, 'side':side, 'split':split,
                                 'execution_seed':'not_supported', 'bootstrap_seed':policy.bootstrap_seed})
                _write(root/'paired-schedule.json', schedule)
                evaluator.evaluate_split(batch, split, baseline_config if side == 'baseline' else candidate_config,
                                         single, directory, reveal_per_task=split=='develop')
                report = json.loads((directory/'evaluation_full.json').read_text(encoding='utf-8'))
                collected[side][split].append(report)
                if len(report['rows']) != len(batch):
                    raise ValueError('paired execution stopped on infrastructure or incomplete evidence')
                for task, row in zip(batch, report['rows'], strict=True):
                    observations[side][split].append(_observation(row['repeats'][0], task, repeat, contract))
    comparisons = {}
    for split in tasks_by_split:
        left, right = observations['baseline'][split], observations['candidate'][split]
        old = {(r.task_id,r.repeat):r for r in left}
        # Critical requirements are compared on the same repeat, never just the representative task.
        for repeat in range(policy.required_repeats):
            a = collected['baseline'][split][repeat]['rows']
            b = collected['candidate'][split][repeat]['rows']
            for before, after in zip(a,b,strict=True):
                statuses = {r['requirement_id']:r['status'] for r in (before.get('score_report') or {}).get('criterion_results',[])}
                new = {r['requirement_id']:r['status'] for r in (after.get('score_report') or {}).get('criterion_results',[])}
                count = sum(statuses.get(k)=='PASS' and new.get(k)!='PASS' for k in after.get('critical_requirements',[]))
                index = next(i for i,r in enumerate(right) if r.task_id==after['task_id'] and r.repeat==repeat)
                right[index] = replace(right[index], critical_regressions=count)
        comparisons[split] = compare_repeated_runs(left, right, policy)
        _write(root/'paired-observations'/f'{split}.json',
               {side:[asdict(r) for r in observations[side][split]] for side in observations})
    reports = {side:{} for side in collected}
    for side in collected:
        for split in tasks_by_split:
            report = _merge(collected[side][split], policy.required_repeats)
            _write(root/side/split/'evaluation_full.json', report)
            reports[side][split] = {k:v for k,v in report.items() if k!='rows'}
            if split=='develop': reports[side][split]['rows']=report['rows']
    eligible = comparisons['develop']['decision']=='eligible_statistical_signal'
    protected = all(not r['blockers'] or set(r['blockers']) <= {'effect_or_interval_inconclusive'}
                    for split,r in comparisons.items() if split!='develop')
    protected = protected and all(all(d >= -policy.max_protected_degradation for d in r.get('per_domain_effect', {}).values())
                                 for split,r in comparisons.items() if split!='develop')
    result = {'eligible':eligible and protected, 'splits':comparisons, 'research_qualified':False,
              'promotion_scope':'engineering', 'execution_seed':'not_supported', 'schedule':schedule}
    _write(root/'paired-comparison.json', result)
    return reports['baseline'], reports['candidate'], result
