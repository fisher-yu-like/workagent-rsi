from __future__ import annotations

from .hashing import canonical_json_hash
from .rsi_contracts import EvaluationContract, PromotionDecision, VerificationReport


class PromotionController:
    def decide(
        self,
        candidate_id: str,
        verification: VerificationReport,
        metrics: dict[str, float | int | bool],
        contract: EvaluationContract,
    ) -> PromotionDecision:
        thresholds = contract.thresholds
        champion_develop = float(metrics.get("champion_develop", 0.0))
        candidate_develop = float(metrics.get("candidate_develop", 0.0))
        gates = {
            "verification": verification.passed,
            "develop": candidate_develop - champion_develop >= float(thresholds.get("develop_gain", 0.0)),
            "critical_regression": int(metrics.get("critical_regressions", 1)) == 0,
            "regression": float(metrics.get("regression_delta", -1.0)) >= -float(thresholds.get("regression_tolerance", 0.0)),
            "hidden": float(metrics.get("hidden_delta", -1.0)) >= -float(thresholds.get("hidden_degradation", 0.0)),
            "ood": float(metrics.get("ood_delta", -1.0)) >= -float(thresholds.get("ood_degradation", 0.0)),
            "unsafe": int(metrics.get("unsafe_actions", 1)) == 0,
            "reproducible": bool(metrics.get("reproducible", False)),
            "cost": float(metrics.get("cost_delta", float("inf"))) <= float(thresholds.get("max_cost_delta", 0.0)),
        }
        decision = "accept" if all(gates.values()) else "reject"
        evidence = canonical_json_hash(
            {
                "candidate_id": candidate_id,
                "verification": verification.model_dump(mode="json"),
                "metrics": metrics,
                "contract": contract.model_dump(mode="json"),
                "gates": gates,
            }
        )
        return PromotionDecision(
            candidate_id=candidate_id,
            decision=decision,
            gate_results=gates,
            develop_delta=candidate_develop - champion_develop,
            regression_delta=float(metrics.get("regression_delta", -1.0)),
            hidden_delta=float(metrics.get("hidden_delta", -1.0)),
            ood_delta=float(metrics.get("ood_delta", -1.0)),
            cost_delta=float(metrics.get("cost_delta", float("inf"))),
            evidence_refs=[evidence],
        )
