from pathlib import Path

import pytest

from workagent_rsi.contracts import TaskSpec
from workagent_rsi.frozen_evaluator import FrozenEvaluator, ResponseJudge
from workagent_rsi.hashing import canonical_json_hash
from workagent_rsi.rsi_contracts import EvaluationContract
from workagent_rsi.skill_runtime import PilotSkillConfig


def tasks():
    return [
        TaskSpec(
            task_id="word-1",
            domain="word",
            instruction="Create document containing REQUIRED-001",
            expected_constraints={"required_text": "REQUIRED-001"},
            hidden_test=True,
        )
    ]


def contract(split_hash: str, evaluator_hash: str):
    return EvaluationContract(
        contract_id="pilot",
        dataset_hash="a" * 64,
        split_hashes={"hidden": split_hash},
        evaluator_hash=evaluator_hash,
        provider_policy="local",
        seeds=[1],
        repeats=1,
        timeout_seconds=60,
        thresholds={},
        git_commit="deadbeef",
    )


def test_frozen_evaluator_rejects_split_hash_mismatch(tmp_path: Path):
    evaluator = FrozenEvaluator("e" * 64)
    with pytest.raises(ValueError, match="split hash"):
        evaluator.evaluate_split(tasks(), "hidden", PilotSkillConfig(marker_source="required_text"), contract("b" * 64, "e" * 64), tmp_path)


def test_hidden_evaluation_redacts_rows_and_automated_judge_can_disagree(tmp_path: Path):
    task_list = tasks()
    split_hash = canonical_json_hash([task.model_dump(mode="json") for task in task_list])
    evaluator = FrozenEvaluator("e" * 64)
    report = evaluator.evaluate_split(
        task_list,
        "hidden",
        PilotSkillConfig(marker_source="task_id"),
        contract(split_hash, "e" * 64),
        tmp_path,
        reveal_per_task=False,
    )
    assert report["score"] == 0.0
    assert "rows" not in report
    assert ResponseJudge().evaluate(task_list, PilotSkillConfig(marker_source="task_id"))["score"] == 1.0
