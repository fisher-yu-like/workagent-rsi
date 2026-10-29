import pytest

from workagent_rsi.study_protocol import prepare_experiment, StudyRecorder


def manifest():
    return prepare_experiment(dict(kind='comparison',model='test',endpoint='https://example.test/v1',
        rounds=3,max_tokens=10000,final_store='private-final',final_hash='a'*64))


def receipt(frozen):
    return dict(manifest_hash=frozen['manifest_hash'],usage=dict(model_calls=3,tool_calls=5,wall_seconds=10,tokens=100),
        includes_optimizer_and_failed_calls=True,fixed_reference={'initial_champion':{},'final_champion':{}},
        paired_comparison={'decision':'inconclusive'})


def test_equal_caps_all_arms_and_cost_of_baseline_is_explicit(tmp_path):
    frozen=manifest()
    assert frozen['arms']['B1']['caps']==frozen['arms']['B2']['caps']==frozen['arms']['B3']['caps']
    assert frozen['all_arm_model_call_cap']==96
    assert frozen['arms']['B0']['equal_cost_claim'] is False
    recorder=StudyRecorder(tmp_path/'study',frozen)
    assert recorder.summarize()['status']=='incomplete'
    for arm in ('B0','B1','B2','B3'):recorder.record_arm(arm,receipt(frozen))
    assert recorder.summarize()['conclusion']=='no_demonstrated_gain'
    assert not recorder.summarize()['research_qualified']
    with pytest.raises(FileExistsError):recorder.record_arm('B3',receipt(frozen))


def test_omitted_failed_calls_unknown_tokens_or_missing_reference_block_receipt(tmp_path):
    frozen=manifest();recorder=StudyRecorder(tmp_path/'study',frozen)
    row=receipt(frozen);row['includes_optimizer_and_failed_calls']=False
    with pytest.raises(ValueError,match='failed calls'):recorder.record_arm('B1',row)
    row=receipt(frozen);row['usage']['tokens']=None
    with pytest.raises(ValueError,match='tokens'):recorder.record_arm('B1',row)
    row=receipt(frozen);row['fixed_reference'].pop('initial_champion')
    with pytest.raises(ValueError,match='both champions'):recorder.record_arm('B1',row)
    with pytest.raises(ValueError,match='all arms'):
        recorder.evaluate_final_once(None,'a'*64,lambda _: {})


def test_six_round_expansion_requires_separate_approval():
    with pytest.raises(ValueError,match='approved expansion'):
        prepare_experiment(dict(kind='comparison',model='test',endpoint='https://example.test/v1',rounds=6))


def test_four_arm_dispatch_preserves_policies_and_resumes_completed_arms(tmp_path):
    from workagent_rsi.study_protocol import execute_comparison
    frozen=manifest();calls=[]
    class FixtureBackend:
        qualification_only=True
        def begin_arm(self,arm,caps,root,*,resume):
            calls.append(('begin',arm));self.arm=arm;return self
        def run_fixed(self,*,repairs):
            calls.append((self.arm,'fixed',repairs));return 'fixed-champion'
        def run_rsi(self,*,rounds,edit_budgets):
            calls.append((self.arm,'rsi',rounds,edit_budgets));return 'selected-champion'
        def reassess_fixed_reference(self,selected):
            calls.append((self.arm,'reference',selected));return {'initial_champion':{},'final_champion':{}}
        def finish(self,selected):return receipt(frozen)
    backend=FixtureBackend()
    report=execute_comparison(frozen,backend,tmp_path/'study')
    assert ('B0','fixed',0) in calls and ('B1','fixed',1) in calls
    assert ('B2','rsi',1,[3]) in calls and ('B3','rsi',3,[3,3,2]) in calls
    assert report['conclusion']=='no_demonstrated_gain' and not report['research_qualified']
    count=len(calls)
    execute_comparison(frozen,backend,tmp_path/'study',resume=True)
    assert len(calls)==count
