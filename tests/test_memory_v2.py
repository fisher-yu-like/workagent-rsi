import pytest

from workagent_rsi.registry import SkillRegistry
from workagent_rsi.candidate_context import LessonRecord, PUBLIC_LESSON


def test_negative_evidence_is_bound_to_parent_and_cohort(tmp_path):
    registry = SkillRegistry(tmp_path)
    registry.record_negative_evidence(skill_id='s', candidate_id='first', parent_version='0.1.0',
        parent_hash='a'*64, cohort_hash='b'*64, patch_hash='c'*64,
        reason='reject', evidence_refs=['d'*64])
    assert registry.has_negative_evidence(skill_id='s', candidate_id='renamed',
        parent_hash='a'*64, cohort_hash='b'*64, patch_hash='c'*64)
    assert not registry.has_negative_evidence(skill_id='s', parent_hash='e'*64,
        cohort_hash='b'*64, patch_hash='c'*64)
    assert not registry.has_negative_evidence(skill_id='s', parent_hash='a'*64,
        cohort_hash='f'*64, patch_hash='c'*64)
    with pytest.raises(ValueError, match='together'):
        registry.has_negative_evidence(skill_id='s', patch_hash='c'*64, parent_hash='a'*64)


def test_package_and_registry_versions_must_agree(tmp_path):
    with pytest.raises(ValueError, match='package version'):
        SkillRegistry(tmp_path).register(skill_id='s', version='0.2.0', package={'version':'0.1.0'},
            manifest={}, parent_version=None, candidate_id=None, status='rejected', evidence_refs=['x'])


def test_lesson_cannot_import_protected_or_arbitrary_text():
    lesson = LessonRecord(evidence_refs=['a'*64], generalized_rule=PUBLIC_LESSON)
    assert lesson.source_split == 'develop'
    for update in ({'source_split':'hidden'}, {'generalized_rule':'Use secret cell B12'},
                   {'excluded_values':['answer']}, {'applicability':['secret-task.xlsx']}):
        with pytest.raises(ValueError):
            LessonRecord.model_validate({**lesson.model_dump(), **update})


def test_budget_resume_retains_interrupted_requests(tmp_path):
    from workagent_rsi.run_budget import RunBudget, BudgetExceeded
    ledger=tmp_path/'budget.json'
    budget=RunBudget(max_model_calls=1)
    with budget.activate(ledger):
        budget.reserve('model')
    resumed=RunBudget.from_ledger(ledger,expected_limits=budget.limits.model_dump())
    assert resumed.snapshot()['used']['model']==1
    assert resumed.snapshot()['cost_known'] is False
    with pytest.raises(BudgetExceeded):
        resumed.reserve('model')
    with pytest.raises(ValueError,match='policy identity'):
        RunBudget.from_ledger(ledger,expected_limits={})
