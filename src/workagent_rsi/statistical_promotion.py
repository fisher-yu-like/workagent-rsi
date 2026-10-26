"""T29 offline comparison core; deliberately not wired into production promotion.

An eligible statistical signal is not research qualification. Source admission,
evaluator qualification, real repeats and execution provenance require the later
controller integration. This module never runs models, workers or promotions.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
import random


@dataclass(frozen=True)
class ComparisonPolicy:
    primary_metric: str = 'auto'
    min_effect: float = .05
    max_protected_degradation: float = .01
    paired_resamples: int = 10000
    bootstrap_seed: int = 20261016
    required_repeats: int = 3
    min_families: int = 8

    def __post_init__(self):
        if self.primary_metric not in {'auto', 'artifact_quality', 'task_success_rate'}:
            raise ValueError('unknown primary metric')
        if self.paired_resamples < 100 or self.required_repeats < 3 or self.min_families < 2:
            raise ValueError('insufficient comparison policy')
        if not math.isfinite(self.min_effect) or not 0 <= self.min_effect <= 1:
            raise ValueError('invalid effect threshold')
        if not math.isfinite(self.max_protected_degradation) or not 0 <= self.max_protected_degradation <= 1:
            raise ValueError('invalid protected-domain threshold')


@dataclass(frozen=True)
class RepeatedObservation:
    task_id: str
    family_id: str
    domain: str
    repeat: int
    execution_id: str
    execution_valid: bool
    execution_succeeded: bool
    quality_score: float | None
    quality_comparable: bool
    judge_observation_id: str | None
    protocol_hash: str
    critical_regressions: int = 0
    unsafe_actions: int = 0

    def __post_init__(self):
        if not all((self.task_id, self.family_id, self.execution_id, self.protocol_hash)):
            raise ValueError('observation identity required')
        if self.domain not in {'excel', 'word', 'powerpoint'} or self.repeat < 0:
            raise ValueError('invalid observation domain or repeat')
        if self.quality_score is not None and (not math.isfinite(self.quality_score) or not 0 <= self.quality_score <= 1):
            raise ValueError('quality score must be finite and bounded')
        if self.critical_regressions < 0 or self.unsafe_actions < 0:
            raise ValueError('negative event count')


def compare_repeated_runs(baseline: list[RepeatedObservation], candidate: list[RepeatedObservation],
                          policy: ComparisonPolicy) -> dict:
    report = {'scope': 'offline_comparison_core_only', 'decision': 'inconclusive',
              'research_qualified': False, 'paired_observations': 0, 'blockers': []}
    blockers = report['blockers']
    maps = []
    for rows in (baseline, candidate):
        lookup = {(r.task_id, r.repeat): r for r in rows}
        if len(lookup) != len(rows):
            blockers.append('duplicate_task_repeat')
        if len({r.execution_id for r in rows}) != len(rows):
            blockers.append('reused_execution')
        maps.append(lookup)
    left, right = maps
    if not left or left.keys() != right.keys():
        blockers.append('unpaired_observation')
    all_rows = baseline + candidate
    if len({r.protocol_hash for r in all_rows}) != 1:
        blockers.append('incomparable_protocol')
    if len({r.execution_id for r in all_rows}) != len(all_rows):
        blockers.append('reused_execution')
    if any(not r.execution_valid for r in all_rows):
        blockers.append('invalid_execution_evidence')
    repeats = defaultdict(set)
    for task, repeat in left:
        repeats[task].add(repeat)
    if any(values != set(range(policy.required_repeats)) for values in repeats.values()):
        blockers.append('missing_or_extra_repeat')
    for key in left.keys() & right.keys():
        a, b = left[key], right[key]
        if (a.family_id, a.domain) != (b.family_id, b.domain):
            blockers.append('changed_pair_identity')
    # A task's family/domain must also stay fixed across its repeats.
    identities = defaultdict(set)
    for row in all_rows:
        identities[row.task_id].add((row.family_id, row.domain))
    if any(len(values) != 1 for values in identities.values()):
        blockers.append('changed_task_identity')
    if blockers:
        report['blockers'] = sorted(set(blockers))
        return report
    pairs = [(left[k], right[k]) for k in sorted(left)]
    report['paired_observations'] = len(pairs)
    has_failure = any(not r.execution_succeeded for r in all_rows)
    required_metric = 'task_success_rate' if has_failure else 'artifact_quality'
    metric = required_metric if policy.primary_metric == 'auto' else policy.primary_metric
    report['primary_metric'] = metric
    if has_failure and metric != 'task_success_rate':
        blockers.append('execution_failures_require_success_metric')
    if metric == 'artifact_quality':
        if any(not r.quality_comparable or r.quality_score is None or not r.judge_observation_id for r in all_rows):
            blockers.append('unqualified_quality_evidence')
        ids = [r.judge_observation_id for r in all_rows]
        if len(set(ids)) != len(ids):
            blockers.append('cached_or_reused_judgement')
    if blockers:
        return report
    value = (lambda r: float(r.execution_succeeded)) if metric == 'task_success_rate' else (lambda r: r.quality_score)
    deltas = [(b.family_id, b.domain, value(b) - value(a)) for a, b in pairs]
    effect = sum(d for _, _, d in deltas) / len(deltas)
    family, domains = defaultdict(list), defaultdict(list)
    for identity, domain, delta in deltas:
        family[identity].append(delta)
        domains[domain].append(delta)
    per_domain = {d: sum(v) / len(v) for d, v in sorted(domains.items())}
    report.update(effect=effect, independent_families=len(family), per_domain_effect=per_domain,
                  per_domain_observations={d: len(v) for d, v in sorted(domains.items())})
    if any(r.critical_regressions for r in candidate):
        blockers.append('critical_regression')
    if any(r.unsafe_actions for r in candidate):
        blockers.append('unsafe_action')
    if any(delta < -policy.max_protected_degradation for delta in per_domain.values()):
        blockers.append('protected_domain_regression')
    if blockers:
        report['decision'] = 'reject'
        return report
    if len(family) < policy.min_families:
        blockers.append('insufficient_independent_families')
        return report
    # Resample whole families. All tasks and all repeats in a sampled family
    # retain their original weights; repeats are not new independent families.
    grouped = [family[k] for k in sorted(family)]
    rng = random.Random(policy.bootstrap_seed)
    samples = []
    for _ in range(policy.paired_resamples):
        sampled = [grouped[rng.randrange(len(grouped))] for _ in grouped]
        samples.append(sum(sum(v) for v in sampled) / sum(len(v) for v in sampled))
    samples.sort()
    interval = [samples[int(.025 * (len(samples) - 1))], samples[int(.975 * (len(samples) - 1))]]
    report.update(confidence_interval=interval, paired_resamples=policy.paired_resamples,
                  bootstrap_seed=policy.bootstrap_seed)
    if effect > policy.min_effect and interval[0] > 0:
        report['decision'] = 'eligible_statistical_signal'
    elif effect <= 0:
        report['decision'] = 'reject'
    else:
        blockers.append('effect_or_interval_inconclusive')
    return report
