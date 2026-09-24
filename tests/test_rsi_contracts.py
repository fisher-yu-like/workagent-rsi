from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from workagent_rsi.hashing import canonical_json_hash, sha256_bytes
from workagent_rsi.rsi_contracts import (
    AtomicEdit,
    CandidatePatch,
    EvaluationContract,
    ExperimentResult,
    PromotionDecision,
)


def test_atomic_edit_rejects_path_escape():
    with pytest.raises(ValidationError):
        AtomicEdit(
            component="prompt",
            target_path="../evaluator.py",
            hypothesis="change",
            expected_metric="success",
            patch="x",
        )


def test_candidate_patch_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        CandidatePatch(
            candidate_id="c1",
            parent_version="0.1.0",
            provider="fake",
            provider_version="1",
            diagnosis_refs=["a" * 64],
            atomic_edits=[
                AtomicEdit(
                    component="prompt",
                    target_path="skill.json",
                    hypothesis="use required marker",
                    expected_metric="task_success_rate",
                    patch='{"marker_source":"required_text"}',
                )
            ],
            edit_budget=1,
            created_at=datetime.now(timezone.utc),
            forbidden="value",
        )


def test_evaluation_contract_hash_is_canonical():
    left = canonical_json_hash({"b": 2, "a": 1})
    right = canonical_json_hash({"a": 1, "b": 2})
    assert left == right == sha256_bytes(b'{"a":1,"b":2}')


def test_contract_and_result_status_are_strict():
    contract = EvaluationContract(
        contract_id="pilot-v1",
        dataset_hash="a" * 64,
        split_hashes={"develop": "b" * 64},
        evaluator_hash="c" * 64,
        provider_policy="codex-local",
        seeds=[20260924],
        repeats=1,
        timeout_seconds=60,
        thresholds={"develop_gain": 0.0},
        git_commit="deadbeef",
    )
    assert contract.contract_id == "pilot-v1"
    with pytest.raises(ValidationError):
        ExperimentResult(
            experiment_id="E01",
            invocation_id="i1",
            status="pending_human_audit",
            contract_hash="d" * 64,
            evidence_refs=["e" * 64],
        )


def test_promotion_decision_requires_evidence():
    with pytest.raises(ValidationError):
        PromotionDecision(
            candidate_id="c1",
            decision="accept",
            gate_results={"verification": True},
            evidence_refs=[],
        )
