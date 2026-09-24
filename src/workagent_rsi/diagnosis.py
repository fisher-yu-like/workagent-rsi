from __future__ import annotations

from typing import Any

from .hashing import canonical_json_hash
from .rsi_contracts import FailureDiagnosis


class FailureDiagnoser:
    """Classify observed public-run failures without inventing missing evidence."""

    def diagnose(self, run_results: list[dict[str, Any]]) -> list[FailureDiagnosis]:
        diagnoses: list[FailureDiagnosis] = []
        for result in run_results:
            if result.get("state") == "SUCCEEDED":
                continue
            message = self._message(result)
            failure_class, component, hypothesis, confidence = self._classify(message)
            run_id = str(result.get("run_id", "unknown"))
            evidence_ref = str(result.get("evidence_ref") or canonical_json_hash(result))
            diagnosis_id = canonical_json_hash(
                {"run_id": run_id, "failure_class": failure_class, "evidence_ref": evidence_ref}
            )[:20]
            diagnoses.append(
                FailureDiagnosis(
                    diagnosis_id=diagnosis_id,
                    run_ids=[run_id],
                    failure_class=failure_class,
                    evidence_refs=[evidence_ref],
                    causal_hypothesis=hypothesis,
                    recommended_component=component,
                    confidence=confidence,
                )
            )
        return diagnoses

    @staticmethod
    def _message(result: dict[str, Any]) -> str:
        parts: list[str] = []
        failure = result.get("failure")
        if isinstance(failure, dict):
            parts.append(str(failure.get("message", "")))
        evaluation = result.get("evaluation")
        if isinstance(evaluation, dict):
            parts.extend(str(item) for item in evaluation.get("critical_failures", []))
        return " ".join(parts).lower()

    @staticmethod
    def _classify(message: str) -> tuple[str, str, str, float]:
        if any(token in message for token in ("unsafe", "forbidden", "permission", "not allowlisted", "leak")):
            if "tool" in message or "allowlisted" in message:
                return "tool", "tool_policy", "tool policy rejected or omitted a required operation", 0.95
            return "safety", "verifier_rule", "candidate or task violated a safety boundary", 0.98
        if any(token in message for token in ("format", "reopen", "docx", "xlsx", "pptx", "media type")):
            return "format", "office_script", "Office package generation or reopening is invalid", 0.95
        if any(token in message for token in ("marker", "required text", "semantic", "missing")):
            return "semantic", "prompt", "generated artifact omitted required task content", 0.9
        if any(token in message for token in ("evaluator", "scoring", "judge unavailable")):
            return "evaluator", "verifier_rule", "evaluation channel is unavailable or inconsistent", 0.9
        if any(token in message for token in ("tool", "timeout", "subprocess", "command")):
            return "tool", "tool_policy", "tool selection or execution failed", 0.85
        if any(token in message for token in ("input", "schema", "validation")):
            return "input", "context", "task input or contract validation failed", 0.85
        if any(token in message for token in ("visual", "overlap", "overflow", "render")):
            return "visual", "office_script", "artifact layout or rendering failed", 0.8
        return "planning", "prompt", "execution failed without a more specific observable class", 0.6
