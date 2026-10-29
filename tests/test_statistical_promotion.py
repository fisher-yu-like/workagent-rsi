from dataclasses import replace

from workagent_rsi.statistical_promotion import ComparisonPolicy, RepeatedObservation, compare_repeated_runs


def observations(deltas):
    baseline, candidate = [], []
    for i, delta in enumerate(deltas):
        for repeat in range(3):
            values = dict(task_id=f't{i}', family_id=f'f{i}', domain=('excel', 'word', 'powerpoint')[i % 3],
                          repeat=repeat, execution_valid=True, execution_succeeded=True,
                          quality_comparable=True, protocol_hash='frozen-test-protocol')
            baseline.append(RepeatedObservation(**values, execution_id=f'b{i}-{repeat}',
                quality_score=.4, judge_observation_id=f'bj{i}-{repeat}'))
            candidate.append(RepeatedObservation(**values, execution_id=f'c{i}-{repeat}',
                quality_score=.4 + delta, judge_observation_id=f'cj{i}-{repeat}'))
    return baseline, candidate


def policy():
    return ComparisonPolicy(paired_resamples=1000, min_families=2)


def test_every_repeat_and_valid_execution_failure_stays_in_denominator():
    baseline, candidate = observations([.2, .2, .2])
    candidate[0] = replace(candidate[0], execution_succeeded=False, quality_score=None,
                           quality_comparable=False, judge_observation_id=None)
    report = compare_repeated_runs(baseline, candidate, policy())
    assert report['paired_observations'] == 9
    assert report['primary_metric'] == 'task_success_rate'
    assert report['effect'] == -1 / 9
    assert report['decision'] == 'reject'


def test_positive_mean_with_interval_crossing_zero_is_inconclusive():
    baseline, candidate = observations([-.4, .6, -.4, .6])
    # Isolate statistical uncertainty from the independent protected-domain gate.
    p = replace(policy(), max_protected_degradation=1.0)
    report = compare_repeated_runs(baseline, candidate, p)
    assert report['effect'] > .05
    assert report['confidence_interval'][0] < 0 < report['confidence_interval'][1]
    assert report['decision'] == 'inconclusive'
    assert report == compare_repeated_runs(baseline, candidate, p)


def test_domain_regression_cannot_be_hidden_by_an_excel_gain():
    baseline, candidate = observations([.5, -.03, .2])
    report = compare_repeated_runs(baseline, candidate, policy())
    assert report['effect'] > .05
    assert report['per_domain_effect']['word'] < -.01
    assert report['decision'] == 'reject'
    candidate[1] = replace(candidate[1], critical_regressions=1)
    assert 'critical_regression' in compare_repeated_runs(baseline, candidate, policy())['blockers']


def test_cached_judgement_and_missing_repeat_do_not_qualify_independence():
    baseline, candidate = observations([.2, .2, .2])
    candidate[1] = replace(candidate[1], judge_observation_id=candidate[0].judge_observation_id)
    report = compare_repeated_runs(baseline, candidate, policy())
    assert report['decision'] == 'inconclusive'
    assert 'cached_or_reused_judgement' in report['blockers']
    report = compare_repeated_runs(baseline, candidate[:-1], policy())
    assert report['decision'] == 'inconclusive'
    assert 'unpaired_observation' in report['blockers']


def test_positive_offline_signal_never_claims_research_qualification():
    baseline, candidate = observations([.2, .2, .2])
    report = compare_repeated_runs(baseline, candidate, policy())
    assert report['decision'] == 'eligible_statistical_signal'
    assert report['research_qualified'] is False
