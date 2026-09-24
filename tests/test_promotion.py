from workagent_rsi.promotion import PromotionController
from workagent_rsi.rsi_contracts import EvaluationContract, VerificationReport


def contract() -> EvaluationContract:
    return EvaluationContract(
        contract_id="pilot",
        dataset_hash="a" * 64,
        split_hashes={"develop": "b" * 64},
        evaluator_hash="c" * 64,
        provider_policy="codex-local",
        seeds=[1],
        repeats=1,
        timeout_seconds=60,
        thresholds={
            "develop_gain": 0.05,
            "regression_tolerance": 0.01,
            "hidden_degradation": 0.01,
            "ood_degradation": 0.01,
            "max_cost_delta": 1.0,
        },
        git_commit="deadbeef",
    )


def verification(passed=True) -> VerificationReport:
    return VerificationReport(
        candidate_id="c1",
        passed=passed,
        critical_violations=[] if passed else ["bad"],
        executed_checks=["schema"],
        evidence_refs=["d" * 64],
    )


def good_metrics():
    return {
        "champion_develop": 0.5,
        "candidate_develop": 0.6,
        "critical_regressions": 0,
        "regression_delta": 0.0,
        "hidden_delta": 0.0,
        "ood_delta": 0.0,
        "unsafe_actions": 0,
        "reproducible": True,
        "cost_delta": 0.2,
    }


def test_promotion_accepts_only_when_all_gates_pass():
    decision = PromotionController().decide("c1", verification(), good_metrics(), contract())
    assert decision.decision == "accept"
    assert all(decision.gate_results.values())


def test_each_noncompensatory_gate_can_reject():
    controller = PromotionController()
    cases = [
        ("verification", verification(False), {}),
        ("develop", verification(), {"candidate_develop": 0.51}),
        ("critical_regression", verification(), {"critical_regressions": 1}),
        ("hidden", verification(), {"hidden_delta": -0.02}),
        ("unsafe", verification(), {"unsafe_actions": 1}),
        ("reproducible", verification(), {"reproducible": False}),
        ("cost", verification(), {"cost_delta": 2.0}),
    ]
    for expected_gate, report, override in cases:
        metrics = good_metrics()
        metrics.update(override)
        decision = controller.decide("c1", report, metrics, contract())
        assert decision.decision == "reject"
        assert decision.gate_results[expected_gate] is False
