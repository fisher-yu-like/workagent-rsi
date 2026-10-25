"""Small independent controls for family grouping and the final-set boundary."""
import json
from pathlib import Path

import pytest

from workagent_rsi.dataset_splits import (
    TaskFamilyManifest, assign_grouped_splits, validate_family_splits,
    split_quality_report, developer_view, SealedFinalStore, prepare_adaptive_splits,
)
from workagent_rsi.contracts import TaskSpec


def row(name='a', split='develop', **kw):
    return TaskFamilyManifest(base_task_id=name, family_id='family-' + name,
        source_document_id='document-' + name, domain='excel',
        variant_ids=[name + '-1', name + '-2', name + '-3'], split=split, **kw)


def test_grouped_assignment_precedes_variants_and_is_reproducible():
    bases = [row(str(i), None).model_copy(update={'variant_ids': [], 'exposure': 'unexposed'}) for i in range(5)]
    targets = {'excel': dict(develop=1, regression=1, promotion_validation=1, final_test=1, ood_transfer=1)}
    result = assign_grouped_splits(bases, targets, seed=17)
    assert result == assign_grouped_splits(list(reversed(bases)), targets, seed=17)
    assert {r.split for r in result} == set(targets['excel'])
    with pytest.raises(ValueError, match='before variants'):
        assign_grouped_splits([row()], targets, seed=17)
    joined = [bases[0], bases[1].model_copy(update={'family_id': bases[0].family_id})]
    with pytest.raises(ValueError, match='insufficient|allocation'):
        assign_grouped_splits(joined, targets, seed=17)


@pytest.mark.parametrize('shared', ['family_id', 'source_document_id', 'source_hash', 'variant_ids', 'base_task_id'])
def test_any_shared_identity_cannot_cross_splits(shared):
    a, b = row('a'), row('b', 'regression')
    value = 'a' * 64 if shared == 'source_hash' else getattr(a, shared)
    a = a.model_copy(update={shared: value})
    b = b.model_copy(update={shared: value})
    with pytest.raises(ValueError, match='overlap|duplicate'):
        validate_family_splits([a, b])


def test_final_content_is_separate_from_developer_and_candidate_views(tmp_path):
    public_root = tmp_path / 'developer'
    public_root.mkdir()
    private_root = tmp_path / 'evaluator'
    secret = 'UNSEEN_FINAL_SECRET_8371'
    final = row('final', 'final_test', exposure='unexposed')
    tasks = {name: TaskSpec(task_id=name, domain='excel', instruction=secret).model_dump(mode='json') for name in final.variant_ids}
    store = SealedFinalStore(private_root, developer_roots=[public_root])
    seal = store.seal([final], tasks)
    view = developer_view([row(), final], seal)
    text = json.dumps(view)
    assert secret not in text and 'family-final' not in text and 'document-final' not in text
    assert str(private_root) not in text and 'final-1' not in text
    assert view['final_test']['task_count'] == 3
    with pytest.raises(ValueError, match='pattern'):
        developer_view([row(), final], {**seal, 'final_test_hash': secret})
    assert seal['final_test_hash'] == store.verify()
    result = store.evaluate_once(seal['final_test_hash'], lambda loaded: {'pass_count': len(loaded)})
    assert result['task_count'] == 3 and 'result_hash' in result
    with pytest.raises(FileExistsError):
        store.evaluate_once(seal['final_test_hash'], lambda loaded: {})
    with pytest.raises(ValueError, match='developer'):
        SealedFinalStore(public_root / 'private', developer_roots=[public_root])
    from workagent_rsi.candidate_workspace import CandidateWorkspaceBuilder
    with pytest.raises(ValueError, match='protected'):
        CandidateWorkspaceBuilder().export(public_root, tmp_path / 'candidate', [], {'final_test/cases.json': secret})


def test_final_input_snapshot_is_hashed_and_tampering_rejected(tmp_path):
    source = tmp_path / 'source.xlsx'
    source.write_bytes(b'authored input bytes')
    family = row('f', 'final_test', exposure='unexposed')
    tasks = {name: TaskSpec(task_id=name, domain='excel', instruction='private', input_files=('source.xlsx',)).model_dump(mode='json') for name in family.variant_ids}
    store = SealedFinalStore(tmp_path / 'private', developer_roots=[tmp_path / 'dev'])
    seal = store.seal([family], tasks, input_files={'source.xlsx': source})
    source.write_bytes(b'later source changes')
    assert store.verify() == seal['final_test_hash']
    next((tmp_path / 'private/inputs').iterdir()).write_bytes(b'tampered')
    with pytest.raises(ValueError, match='hash'):
        store.verify()


def test_final_seal_rejects_exposed_content_and_incomplete_task_binding(tmp_path):
    for name, family, tasks in [('exposed', row('f', 'final_test'), {}),
                                ('missing', row('f', 'final_test', exposure='unexposed'), {})]:
        store = SealedFinalStore(tmp_path / name, developer_roots=[tmp_path / 'dev'])
        with pytest.raises(ValueError, match='exposed|binding'):
            store.seal([family], tasks)
        assert not (tmp_path / name).exists()


def test_insufficient_families_are_blocked_not_padded():
    report = split_quality_report([row()])
    assert report['status'] == 'blocked'
    assert report['target_base_tasks'] == 72 and report['target_instances'] == 216
    assert report['actual_base_tasks'] == 1 and report['actual_instances'] == 3
    assert report['final_test_count'] == 0 and report['blockers']
    with pytest.raises(ValueError, match='exposed'):
        validate_family_splits([row('f', 'final_test')])


def test_legacy_hidden_mapping_is_explicit_and_final_never_enters_adaptive_loop():
    task = TaskSpec(task_id='a', domain='excel', instruction='public')
    legacy = {split: [task] for split in ['develop', 'regression', 'hidden', 'ood_transfer']}
    with pytest.raises(ValueError, match='mapping'):
        prepare_adaptive_splits(legacy)
    mapped, record = prepare_adaptive_splits(legacy, legacy_hidden_mapping='promotion_validation')
    assert 'hidden' in mapped and record['legacy_hidden_maps_to'] == 'promotion_validation'
    assert record['untouched_final_test_claim'] is False
    modern = {('promotion_validation' if k == 'hidden' else k): v for k, v in legacy.items()}
    _, record = prepare_adaptive_splits(modern)
    assert record['internal_hidden_role'] == 'promotion_validation'
    modern['final_test'] = [task]
    with pytest.raises(ValueError, match='final_test'):
        prepare_adaptive_splits(modern)


def test_runner_applies_mapping_before_execution_and_writes_role_record(tmp_path, monkeypatch):
    from workagent_rsi.workagent_experiment import WorkAgentExperimentRunner
    from workagent_rsi.workagent_provider import WorkAgentSkill
    runner = WorkAgentExperimentRunner()
    task = TaskSpec(task_id='public', domain='excel', instruction='public')
    modern = {s: [task] for s in ['develop', 'regression', 'promotion_validation', 'ood_transfer']}
    captured = []
    monkeypatch.setattr(runner, '_run', lambda tasks, *a, **kw: captured.append(tasks) or {'captured': True})
    runner.run(modern, WorkAgentSkill(instructions='general'), object(), tmp_path / 'run')
    assert set(captured[0]) == {'develop', 'regression', 'hidden', 'ood_transfer'}
    assert captured[0]['hidden'][0].hidden_test is True
    record = json.loads((tmp_path / 'run/split-roles.json').read_text())
    assert record['internal_hidden_role'] == 'promotion_validation' and record['final_test_used'] is False
    with pytest.raises(ValueError, match='final_test'):
        runner.run({**modern, 'final_test': [task]}, WorkAgentSkill(instructions='general'), object(), tmp_path / 'never')
    assert not (tmp_path / 'never').exists()


def test_runner_rejects_formal_inventory_gaps_before_creating_output(tmp_path):
    from workagent_rsi.workagent_experiment import WorkAgentExperimentRunner
    from workagent_rsi.workagent_provider import WorkAgentSkill
    task = TaskSpec(task_id='a', domain='excel', instruction='public')
    modern = {s: [task] for s in ['develop', 'regression', 'promotion_validation', 'ood_transfer']}
    with pytest.raises(ValueError, match='isolated family manifest'):
        WorkAgentExperimentRunner().run(modern, WorkAgentSkill(instructions='general'), object(), tmp_path / 'never', mode='formal')
    assert not (tmp_path / 'never').exists()


def test_final_callback_failure_consumes_set_and_mutation_cannot_pass(tmp_path):
    family = row('f', 'final_test', exposure='unexposed')
    tasks = {name: TaskSpec(task_id=name, domain='excel', instruction='private').model_dump(mode='json') for name in family.variant_ids}
    for mode in ['failure', 'mutation']:
        store = SealedFinalStore(tmp_path / mode, developer_roots=[tmp_path / 'dev'])
        seal = store.seal([family], tasks)
        def callback(_):
            if mode == 'failure':
                raise RuntimeError('evaluation failed')
            path = tmp_path / mode / 'sealed-final.json'
            path.write_text(path.read_text() + ' ')
            return {}
        with pytest.raises((RuntimeError, ValueError)):
            store.evaluate_once(seal['final_test_hash'], callback)
        assert (tmp_path / mode / 'consumed.json').exists()
