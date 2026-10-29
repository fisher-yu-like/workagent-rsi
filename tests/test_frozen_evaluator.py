from pathlib import Path

import pytest

from workagent_rsi.contracts import TaskSpec
from workagent_rsi.frozen_evaluator import FrozenEvaluator, ResponseJudge
from workagent_rsi.evaluator import OfficeArtifactEvaluator
from workagent_rsi.hashing import canonical_json_hash
from workagent_rsi.rsi_contracts import EvaluationContract
from workagent_rsi.skill_runtime import PilotSkillConfig
from workagent_rsi.skill_runtime import SkillConfiguredOfficeAdapter
from workagent_rsi.storage import ArtifactStore
from docx import Document
from model_fixture import MarkerFixtureAssessment


def tasks():
    return [
        TaskSpec(
            task_id="word-1",
            domain="word",
            instruction="Create a document with the required marker",
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
    evaluator = FrozenEvaluator("e" * 64, assessment=MarkerFixtureAssessment())
    with pytest.raises(ValueError, match="split hash"):
        evaluator.evaluate_split(
            tasks(),
            "hidden",
            PilotSkillConfig(marker_source="required_text"),
            contract("b" * 64, "e" * 64),
            tmp_path,
        )


def test_hidden_evaluation_redacts_rows_and_detects_bad_baseline(tmp_path: Path):
    task_list = tasks()
    bad_events = list(
        SkillConfiguredOfficeAdapter(
            tmp_path / "bad", PilotSkillConfig(marker_source="task_id")
        ).execute(task_list[0], "office.marker")
    )
    bad_document = Document(bad_events[-1]["artifact_path"])
    assert "REQUIRED-001" not in "\n".join(
        paragraph.text for paragraph in bad_document.paragraphs
    )
    good_events = list(
        SkillConfiguredOfficeAdapter(
            tmp_path / "good", PilotSkillConfig(marker_source="required_text")
        ).execute(task_list[0], "office.marker")
    )
    good_document = Document(good_events[-1]["artifact_path"])
    assert "REQUIRED-001" in "\n".join(
        paragraph.text for paragraph in good_document.paragraphs
    )
    split_hash = canonical_json_hash(
        [task.model_dump(mode="json") for task in task_list]
    )
    evaluator = FrozenEvaluator("e" * 64, assessment=MarkerFixtureAssessment())
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


def test_response_only_judge_can_disagree_with_artifact_check(tmp_path: Path):
    task = TaskSpec(
        task_id="word-1",
        domain="word",
        instruction="Create document containing REQUIRED-001",
        expected_constraints={"required_text": "REQUIRED-001"},
    )
    path = tmp_path / "missing-marker.docx"
    document = Document()
    document.add_heading("Generated Artifact", level=1)
    document.add_paragraph("word-1")
    document.save(path)
    ref = ArtifactStore(tmp_path / "artifacts").put_file(
        path, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    artifact_report = OfficeArtifactEvaluator(assessment_profile="legacy").evaluate(
        task, [ref], "test"
    )
    response_report = ResponseJudge().evaluate(
        [task], PilotSkillConfig(marker_source="task_id")
    )

    assert artifact_report.score is None
    assert response_report["score"] is None
