from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from .candidate_provider import CandidateProvider
from .candidate_workspace import CandidateWorkspaceBuilder
from .contracts import TaskSpec
from .diagnosis import FailureDiagnoser
from .frozen_evaluator import FrozenEvaluator
from .hashing import canonical_json_hash
from .promotion import PromotionController
from .registry import SkillRegistry
from .rsi_contracts import EvaluationContract
from .skill_runtime import PilotSkillConfig
from .verifier import CandidateVerifier, VerificationPolicy


class RSILoop:
    def __init__(
        self,
        *,
        registry: SkillRegistry,
        workspace_builder: CandidateWorkspaceBuilder,
        provider: CandidateProvider,
        verifier: CandidateVerifier,
        evaluator: FrozenEvaluator,
        promotion: PromotionController,
    ) -> None:
        self.registry = registry
        self.workspace_builder = workspace_builder
        self.provider = provider
        self.verifier = verifier
        self.evaluator = evaluator
        self.promotion = promotion

    def run_round(
        self,
        *,
        skill_id: str,
        tasks_by_split: dict[str, Sequence[TaskSpec]],
        contract: EvaluationContract,
        source_root: str | Path,
        run_root: str | Path,
        verification_policy: VerificationPolicy,
    ) -> dict:
        root = Path(run_root)
        root.mkdir(parents=True, exist_ok=True)
        champion = self.registry.champion(skill_id)
        champion_package = self.registry.package(champion)
        champion_config = PilotSkillConfig.model_validate(champion_package)
        baseline = self._evaluate_all(tasks_by_split, champion_config, contract, root / "baseline")
        public_rows = baseline.get("develop", {}).get("rows", [])
        diagnosis_input = [
            {
                "run_id": f"baseline-{row['task_id']}",
                "state": "SUCCEEDED" if row.get("passed") else "FAILED",
                "evaluation": {"critical_failures": row.get("critical_failures", [])},
                "evidence_ref": canonical_json_hash(row),
            }
            for row in public_rows
        ]
        diagnoses = FailureDiagnoser().diagnose(diagnosis_input)
        workspace = root / "candidate_workspace"
        self.workspace_builder.export(
            source_root,
            workspace,
            allowed_files=["skill.json"],
            context_files={
                "diagnoses.json": json.dumps([item.model_dump(mode="json") for item in diagnoses], indent=2, sort_keys=True),
            },
        )
        candidate, provider_record = self.provider.generate(
            workspace,
            diagnoses,
            champion.version,
            1,
            root / "provider_records",
        )
        if candidate is None:
            return {"status": provider_record.status, "provider_record": provider_record.model_dump(mode="json"), "baseline": baseline}
        verification = self.verifier.verify(candidate, workspace, verification_policy)
        if verification.passed:
            candidate_package = dict(champion_package)
            for edit in candidate.atomic_edits:
                candidate_package.update(json.loads(edit.patch))
            candidate_config = PilotSkillConfig.model_validate(candidate_package)
            candidate_reports = self._evaluate_all(tasks_by_split, candidate_config, contract, root / "candidate")
        else:
            candidate_package = dict(champion_package)
            candidate_reports = {}
        metrics = self._metrics(baseline, candidate_reports, verification.passed)
        decision = self.promotion.decide(candidate.candidate_id, verification, metrics, contract)
        version = self._next_version(champion.version)
        record = self.registry.register(
            skill_id=skill_id,
            version=version,
            package=candidate_package,
            manifest={"domain": "office", "provider": candidate.provider},
            parent_version=champion.version,
            candidate_id=candidate.candidate_id,
            status="accepted" if decision.decision == "accept" else "rejected",
            evidence_refs=decision.evidence_refs,
        )
        if decision.decision == "accept":
            self.registry.set_champion(skill_id, record.version, decision.evidence_refs)
        result = {
            "status": "completed",
            "champion_before": champion.model_dump(mode="json"),
            "candidate": candidate.model_dump(mode="json"),
            "provider_record": provider_record.model_dump(mode="json"),
            "verification": verification.model_dump(mode="json"),
            "baseline": baseline,
            "candidate_reports": candidate_reports,
            "metrics": metrics,
            "decision": decision.model_dump(mode="json"),
            "registered_version": record.model_dump(mode="json"),
        }
        (root / "round_summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result

    def _evaluate_all(
        self,
        tasks_by_split: dict[str, Sequence[TaskSpec]],
        config: PilotSkillConfig,
        contract: EvaluationContract,
        root: Path,
    ) -> dict[str, dict]:
        reports: dict[str, dict] = {}
        for split, tasks in tasks_by_split.items():
            if not tasks:
                continue
            reports[split] = self.evaluator.evaluate_split(
                tasks,
                split,
                config,
                contract,
                root / split,
                reveal_per_task=split != "hidden",
            )
        return reports

    @staticmethod
    def _metrics(baseline: dict[str, dict], candidate: dict[str, dict], verified: bool) -> dict[str, float | int | bool]:
        def score(bundle: dict[str, dict], split: str) -> float:
            return float(bundle.get(split, {}).get("score", 0.0))

        baseline_reg = {row["task_id"]: row["passed"] for row in baseline.get("regression", {}).get("rows", [])}
        candidate_reg = {row["task_id"]: row["passed"] for row in candidate.get("regression", {}).get("rows", [])}
        critical = sum(bool(passed) and not bool(candidate_reg.get(task_id)) for task_id, passed in baseline_reg.items())
        return {
            "champion_develop": score(baseline, "develop"),
            "candidate_develop": score(candidate, "develop") if verified else 0.0,
            "critical_regressions": critical,
            "regression_delta": score(candidate, "regression") - score(baseline, "regression"),
            "hidden_delta": score(candidate, "hidden") - score(baseline, "hidden"),
            "ood_delta": score(candidate, "ood_transfer") - score(baseline, "ood_transfer"),
            "unsafe_actions": 0,
            "reproducible": verified,
            "cost_delta": 0.1,
        }

    @staticmethod
    def _next_version(version: str) -> str:
        major, minor, patch = (int(item) for item in version.split("."))
        return f"{major}.{minor + 1}.{patch}"
