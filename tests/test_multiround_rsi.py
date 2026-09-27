from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

import pytest

from workagent_rsi.candidate_provider import DeterministicCandidateProvider
from workagent_rsi.candidate_workspace import CandidateWorkspaceBuilder
from workagent_rsi.contracts import TaskSpec
from workagent_rsi.frozen_evaluator import FrozenEvaluator
from workagent_rsi.hashing import canonical_json_hash
from workagent_rsi.promotion import PromotionController
from workagent_rsi.registry import SkillRegistry
from workagent_rsi.rsi_contracts import EvaluationContract, ProviderRecord
from workagent_rsi.rsi_loop import RSILoop
from workagent_rsi.verifier import CandidateVerifier, VerificationPolicy


def _task() -> TaskSpec:
    return TaskSpec(
        task_id="excel-rsi",
        domain="excel",
        instruction="Create a workbook containing REQUIRED-RSI",
        expected_constraints={"required_text": "REQUIRED-RSI"},
    )


def _contract(task: TaskSpec) -> EvaluationContract:
    split_hash = canonical_json_hash([task.model_dump(mode="json")])
    return EvaluationContract(
        contract_id="multiround",
        dataset_hash=canonical_json_hash({"develop": split_hash}),
        split_hashes={"develop": split_hash},
        evaluator_hash="e" * 64,
        provider_policy="deterministic",
        seeds=[1],
        repeats=1,
        timeout_seconds=60,
        thresholds={
            "develop_gain": 0.05,
            "regression_tolerance": 1.0,
            "hidden_degradation": 1.0,
            "ood_degradation": 1.0,
            "max_cost_delta": 1.0,
        },
        git_commit="test",
    )


def _loop(tmp_path: Path, provider=None) -> RSILoop:
    registry = SkillRegistry(tmp_path / "registry")
    registry.register(
        skill_id="office.marker",
        version="0.1.0",
        package={"marker_source": "task_id"},
        manifest={"domain": "office"},
        parent_version=None,
        candidate_id=None,
        status="champion",
        evidence_refs=["a" * 64],
    )
    source = tmp_path / "source"
    source.mkdir()
    (source / "skill.json").write_text(json.dumps({"marker_source": "task_id"}), encoding="utf-8")
    return RSILoop(
        registry=registry,
        workspace_builder=CandidateWorkspaceBuilder(),
        provider=provider or DeterministicCandidateProvider(),
        verifier=CandidateVerifier(),
        evaluator=FrozenEvaluator("e" * 64),
        promotion=PromotionController(),
    )


def test_six_round_run_records_budget_cost_checkpoint_and_inheritance(tmp_path: Path):
    task = _task()
    run_root = tmp_path / "run"
    loop = _loop(tmp_path)
    result = loop.run(
        skill_id="office.marker",
        tasks_by_split={"develop": [task]},
        contract=_contract(task),
        source_root=tmp_path / "source",
        run_root=run_root,
        verification_policy=VerificationPolicy(allowed_targets={"skill.json"}),
    )

    assert result["status"] == "completed"
    assert result["round_count"] == 6
    assert [row["edit_budget"] for row in result["rounds"]] == [3, 3, 2, 2, 1, 1]
    assert all("costs" in row for row in result["rounds"])
    assert all("actual_edit_count" in row for row in result["rounds"])
    assert result["rounds"][1]["champion_before"]["version"] == result["rounds"][0]["champion_after"]["version"]
    assert result["rounds"][1]["inherited_evidence_refs"]
    assert (run_root / "checkpoint.json").exists()
    checkpoint = json.loads((run_root / "checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["status"] == "completed"
    assert checkpoint["completed_rounds"] == 6
    assert any(row.get("candidate_status") == "pruned_negative_evidence" for row in result["rounds"])
    assert all(0 <= value <= 1 for row in result["rounds"] for split in row.get("candidate_reports", {}).values() for task_row in split.get("rows", []) for value in task_row.get("dimensions", {}).values())


def test_resume_rejects_contract_identity_change_and_does_not_rerun_completed_rounds(tmp_path: Path):
    task = _task()
    run_root = tmp_path / "run"
    loop = _loop(tmp_path)
    contract = _contract(task)
    first = loop.run(
        skill_id="office.marker",
        tasks_by_split={"develop": [task]},
        contract=contract,
        source_root=tmp_path / "source",
        run_root=run_root,
        verification_policy=VerificationPolicy(allowed_targets={"skill.json"}),
        rounds=2,
    )
    resumed = loop.run(
        skill_id="office.marker",
        tasks_by_split={"develop": [task]},
        contract=contract,
        source_root=tmp_path / "source",
        run_root=run_root,
        resume_root=run_root,
        verification_policy=VerificationPolicy(allowed_targets={"skill.json"}),
        rounds=2,
    )
    assert resumed["round_count"] == first["round_count"] == 2
    assert resumed["resumed"] is True
    changed = contract.model_copy(update={"contract_id": "changed"})
    with pytest.raises(ValueError, match="contract"):
        loop.run(
            skill_id="office.marker",
            tasks_by_split={"develop": [task]},
            contract=changed,
            source_root=tmp_path / "source",
            run_root=run_root,
            resume_root=run_root,
            verification_policy=VerificationPolicy(allowed_targets={"skill.json"}),
            rounds=2,
        )


class InterruptSecondRoundProvider:
    provider_version = "interrupt-once-test"

    def __init__(self):
        self.calls = 0
        self.skill_markers: list[str] = []
        self.delegate = DeterministicCandidateProvider()

    def generate(self, workspace, diagnoses, parent_version, edit_budget, record_root):
        self.calls += 1
        package = json.loads((Path(workspace) / "skill.json").read_text(encoding="utf-8"))
        self.skill_markers.append(package["marker_source"])
        if self.calls == 2:
            now = datetime.now(timezone.utc)
            record = ProviderRecord(
                provider="interrupt-once-test",
                provider_version=self.provider_version,
                command=[],
                prompt_hash="a" * 64,
                workspace_hash="b" * 64,
                started_at=now,
                ended_at=now,
                exit_code=None,
                status="unavailable",
                error="controlled interruption between completed and pending rounds",
            )
            return None, record
        return self.delegate.generate(workspace, diagnoses, parent_version, edit_budget, record_root)


class UniqueCandidateProvider:
    provider_version = "unique-candidate-test"

    def __init__(self):
        self.calls = 0
        self.delegate = DeterministicCandidateProvider()

    def generate(self, workspace, diagnoses, parent_version, edit_budget, record_root):
        self.calls += 1
        candidate, record = self.delegate.generate(workspace, diagnoses, parent_version, edit_budget, record_root)
        return candidate.model_copy(update={"candidate_id": f"candidate-{self.calls}"}), record


def test_rejected_sibling_candidates_receive_unique_registry_versions(tmp_path: Path):
    task = _task()
    loop = _loop(tmp_path, UniqueCandidateProvider())
    result = loop.run(
        skill_id="office.marker",
        tasks_by_split={"develop": [task]},
        contract=_contract(task),
        source_root=tmp_path / "source",
        run_root=tmp_path / "run",
        verification_policy=VerificationPolicy(allowed_targets={"skill.json"}),
        rounds=3,
    )

    assert result["status"] == "completed"
    assert [row["registered_version"]["version"] for row in result["rounds"]] == ["0.2.0", "0.3.0", "0.4.0"]


def test_resume_retries_only_incomplete_round_and_uses_latest_champion(tmp_path: Path):
    task = _task()
    provider = InterruptSecondRoundProvider()
    loop = _loop(tmp_path, provider)
    run_root = tmp_path / "run"
    arguments = {
        "skill_id": "office.marker",
        "tasks_by_split": {"develop": [task]},
        "contract": _contract(task),
        "source_root": tmp_path / "source",
        "run_root": run_root,
        "verification_policy": VerificationPolicy(allowed_targets={"skill.json"}),
        "rounds": 2,
    }

    interrupted = loop.run(**arguments)

    assert interrupted["status"] == "incomplete"
    assert interrupted["round_count"] == 1
    first_round = json.loads((run_root / "checkpoint.json").read_text(encoding="utf-8"))["rounds"][0]
    assert first_round["champion_after"]["version"] == "0.2.0"

    resumed = loop.run(**{**arguments, "resume_root": run_root})

    assert resumed["status"] == "completed"
    assert resumed["resumed"] is True
    assert resumed["round_count"] == 2
    assert provider.calls == 3
    assert provider.skill_markers == ["task_id", "required_text", "required_text"]
    assert resumed["rounds"][0] == first_round
    assert resumed["rounds"][1]["champion_before"]["version"] == "0.2.0"

