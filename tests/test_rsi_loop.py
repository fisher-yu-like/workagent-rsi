import json
from pathlib import Path

from workagent_rsi.candidate_provider import DeterministicCandidateProvider
from workagent_rsi.candidate_workspace import CandidateWorkspaceBuilder
from workagent_rsi.contracts import TaskSpec
from workagent_rsi.frozen_evaluator import FrozenEvaluator
from workagent_rsi.hashing import canonical_json_hash
from workagent_rsi.promotion import PromotionController
from workagent_rsi.registry import RollbackManager, SkillRegistry
from workagent_rsi.rsi_contracts import EvaluationContract
from workagent_rsi.rsi_loop import RSILoop
from workagent_rsi.verifier import CandidateVerifier, VerificationPolicy


def test_fake_provider_closed_loop_promotes_and_rolls_back(tmp_path: Path):
    task = TaskSpec(
        task_id="word-1",
        domain="word",
        instruction="Create REQUIRED-001",
        expected_constraints={"required_text": "REQUIRED-001"},
    )
    split_hash = canonical_json_hash([task.model_dump(mode="json")])
    contract = EvaluationContract(
        contract_id="pilot",
        dataset_hash="a" * 64,
        split_hashes={"develop": split_hash},
        evaluator_hash="e" * 64,
        provider_policy="deterministic",
        seeds=[1],
        repeats=1,
        timeout_seconds=60,
        thresholds={"develop_gain": 0.1, "regression_tolerance": 1.0, "hidden_degradation": 1.0, "ood_degradation": 1.0, "max_cost_delta": 1.0},
        git_commit="deadbeef",
    )
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
    loop = RSILoop(
        registry=registry,
        workspace_builder=CandidateWorkspaceBuilder(),
        provider=DeterministicCandidateProvider(),
        verifier=CandidateVerifier(),
        evaluator=FrozenEvaluator("e" * 64),
        promotion=PromotionController(),
    )
    result = loop.run_round(
        skill_id="office.marker",
        tasks_by_split={"develop": [task]},
        contract=contract,
        source_root=source,
        run_root=tmp_path / "run",
        verification_policy=VerificationPolicy(allowed_targets={"skill.json"}),
    )
    assert result["decision"]["decision"] == "accept"
    assert registry.champion("office.marker").version == "0.2.0"
    RollbackManager(registry).rollback("office.marker", "0.1.0", ["f" * 64])
    assert registry.champion("office.marker").version == "0.1.0"
