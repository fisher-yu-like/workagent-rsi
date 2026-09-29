from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel

from .candidate_provider import CandidateProvider
from .candidate_workspace import CandidateWorkspaceBuilder
from .contracts import TaskSpec
from .costs import measure_round_cost
from .diagnosis import FailureDiagnoser
from .frozen_evaluator import FrozenEvaluator
from .hashing import canonical_json_hash
from .promotion import PromotionController
from .registry import SkillRegistry
from .rsi_contracts import EvaluationContract
from .skill_runtime import PilotSkillConfig
from .verifier import CandidateVerifier, VerificationPolicy
from .workagent_provider import WorkAgentSkill


DEFAULT_EDIT_BUDGETS = (3, 3, 2, 2, 1, 1)


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
        skill_model: type[BaseModel] = PilotSkillConfig,
    ) -> None:
        self.registry = registry
        self.workspace_builder = workspace_builder
        self.provider = provider
        self.verifier = verifier
        self.evaluator = evaluator
        self.promotion = promotion
        self.skill_model = skill_model

    def run(
        self,
        *,
        skill_id: str,
        tasks_by_split: dict[str, Sequence[TaskSpec]],
        contract: EvaluationContract,
        source_root: str | Path,
        run_root: str | Path,
        verification_policy: VerificationPolicy,
        rounds: int = 6,
        resume_root: str | Path | None = None,
        edit_budgets: Sequence[int] | None = None,
        model_identity: str | None = None,
    ) -> dict:
        """Run or resume a bounded multi-round RSI experiment."""

        if rounds < 1:
            raise ValueError("rounds must be at least 1")
        budgets = [int(value) for value in (edit_budgets or DEFAULT_EDIT_BUDGETS)]
        if len(budgets) < rounds or any(value < 1 for value in budgets[:rounds]):
            raise ValueError("edit_budgets must contain a positive budget for every requested round")
        self._validate_task_splits(tasks_by_split, contract)
        root = Path(resume_root if resume_root is not None else run_root)
        checkpoint_path = root / "checkpoint.json"
        identity = self._identity(contract, tasks_by_split, model_identity)
        resumed = resume_root is not None
        rounds_data: list[dict] = []
        attempts: dict[str, int] = {}

        if checkpoint_path.exists():
            if resume_root is None:
                raise FileExistsError(f"checkpoint exists; pass resume_root to continue: {checkpoint_path}")
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            self._validate_checkpoint(checkpoint, identity)
            rounds_data = list(checkpoint.get("rounds", []))
            attempts = {str(key): int(value) for key, value in checkpoint.get("attempts", {}).items()}
            if checkpoint.get("status") == "completed" and len(rounds_data) >= rounds:
                summary_path = root / "run_summary.json"
                summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else self._summary(identity, rounds_data, root, status="completed")
                summary["resumed"] = True
                return summary
        else:
            if root.exists() and any(root.iterdir()):
                raise FileExistsError(f"run root is not empty: {root}")
            root.mkdir(parents=True, exist_ok=True)
            self._write_checkpoint(
                checkpoint_path,
                {
                    **identity,
                    "status": "in_progress",
                    "rounds_requested": rounds,
                    "edit_budgets": budgets[:rounds],
                    "completed_rounds": 0,
                    "rounds": [],
                    "attempts": {},
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        start_index = len(rounds_data)
        for round_index in range(start_index, rounds):
            round_number = round_index + 1
            attempt = attempts.get(str(round_number), 0) + 1
            attempts[str(round_number)] = attempt
            round_root = root / f"round-{round_number:02d}" if attempt == 1 else root / f"round-{round_number:02d}-retry-{attempt:02d}"
            started = time.perf_counter()
            inherited_refs = self._inherited_evidence(rounds_data)
            round_source = self._materialize_source_snapshot(skill_id, root, round_number, attempt)
            try:
                round_result = self.run_round(
                    skill_id=skill_id,
                    tasks_by_split=tasks_by_split,
                    contract=contract,
                    source_root=round_source,
                    run_root=round_root,
                    verification_policy=verification_policy,
                    edit_budget=budgets[round_index],
                    round_index=round_number,
                    inherited_evidence_refs=inherited_refs,
                )
            except Exception as exc:
                checkpoint = {
                    **identity,
                    "status": "in_progress",
                    "rounds_requested": rounds,
                    "edit_budgets": budgets[:rounds],
                    "completed_rounds": len(rounds_data),
                    "rounds": rounds_data,
                    "attempts": attempts,
                    "failure": str(exc),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                self._write_checkpoint(checkpoint_path, checkpoint)
                return {**self._summary(identity, rounds_data, root, status="failed"), "resumed": resumed, "failure": str(exc)}
            round_result["costs"] = measure_round_cost(round_root, started)
            round_result["edit_budget"] = budgets[round_index]
            round_result["actual_edit_count"] = int(round_result.get("actual_edit_count", 0))
            round_result["round_root"] = str(round_root.resolve())
            self._write_round_summary(round_root, round_result)
            (round_root / "cost.json").write_text(json.dumps(round_result["costs"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if round_result.get("status") == "no_candidate_needed":
                rounds_data.append(round_result)
                summary = self._summary(identity, rounds_data, root, status="no_candidate_needed")
                (root / "run_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                return summary
            if round_result.get("status") in {"unavailable", "timeout", "failed", "incomplete"}:
                checkpoint = {
                    **identity,
                    "status": "in_progress",
                    "rounds_requested": rounds,
                    "edit_budgets": budgets[:rounds],
                    "completed_rounds": len(rounds_data),
                    "rounds": rounds_data,
                    "attempts": attempts,
                    "incomplete_round": round_result,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                self._write_checkpoint(checkpoint_path, checkpoint)
                return {**self._summary(identity, rounds_data, root, status="incomplete"), "resumed": resumed, "incomplete_round": round_result}

            rounds_data.append(round_result)
            self._write_checkpoint(
                checkpoint_path,
                {
                    **identity,
                    "status": "in_progress" if len(rounds_data) < rounds else "completed",
                    "rounds_requested": rounds,
                    "edit_budgets": budgets[:rounds],
                    "completed_rounds": len(rounds_data),
                    "rounds": rounds_data,
                    "attempts": attempts,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        summary = self._summary(identity, rounds_data, root, status="completed")
        summary["resumed"] = resumed
        (root / "run_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return summary

    def run_round(
        self,
        *,
        skill_id: str,
        tasks_by_split: dict[str, Sequence[TaskSpec]],
        contract: EvaluationContract,
        source_root: str | Path,
        run_root: str | Path,
        verification_policy: VerificationPolicy,
        edit_budget: int = 1,
        round_index: int = 1,
        inherited_evidence_refs: Sequence[str] | None = None,
    ) -> dict:
        root = Path(run_root)
        root.mkdir(parents=True, exist_ok=True)
        champion = self.registry.champion(skill_id)
        champion_package = self.registry.package(champion)
        champion_config = self.skill_model.model_validate(champion_package)
        rollback_point = {
            "skill_id": skill_id,
            "version": champion.version,
            "content_hash": champion.content_hash,
            "evidence_refs": list(champion.evidence_refs),
        }
        baseline = self._evaluate_all(tasks_by_split, champion_config, contract, root / "baseline")
        if self._is_workagent and self._incomplete(baseline, tasks_by_split):
            result = {"status": "incomplete", "round_index": round_index, "champion_before": champion.model_dump(mode="json"),
                      "champion_after": champion.model_dump(mode="json"), "rollback_point": rollback_point, "baseline": baseline,
                      "actual_edit_count": 0}
            self._write_round_summary(root, result)
            return result
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
        if self._is_workagent and not diagnoses:
            result = {"status": "no_candidate_needed", "round_index": round_index,
                      "champion_before": champion.model_dump(mode="json"), "champion_after": champion.model_dump(mode="json"),
                      "rollback_point": rollback_point, "baseline": baseline, "actual_edit_count": 0}
            self._write_round_summary(root, result)
            return result
        workspace = root / "candidate_workspace"
        self.workspace_builder.export(
            source_root,
            workspace,
            allowed_files=["skill.json"],
            context_files={
                "diagnoses.json": json.dumps([item.model_dump(mode="json") for item in diagnoses], indent=2, sort_keys=True),
                "inherited_evidence.json": json.dumps(list(inherited_evidence_refs or []), indent=2),
            },
        )
        candidate, provider_record = self.provider.generate(
            workspace,
            diagnoses,
            champion.version,
            edit_budget,
            root / "provider_records",
        )
        if candidate is None:
            result = {
                "status": provider_record.status,
                "round_index": round_index,
                "champion_before": champion.model_dump(mode="json"),
                "champion_after": champion.model_dump(mode="json"),
                "rollback_point": rollback_point,
                "inherited_evidence_refs": list(inherited_evidence_refs or []),
                "edit_budget": edit_budget,
                "actual_edit_count": 0,
                "provider_record": provider_record.model_dump(mode="json"),
                "baseline": baseline,
            }
            self._write_round_summary(root, result)
            return result

        if self._is_workagent:
            try:
                if candidate.edit_budget > edit_budget or len(candidate.atomic_edits) > edit_budget or candidate.new_tests:
                    raise ValueError("WorkAgent candidate exceeds instruction edit budget")
                for edit in candidate.atomic_edits:
                    payload = json.loads(edit.patch)
                    if edit.target_path != "skill.json" or set(payload) != {"instructions"} or not isinstance(payload["instructions"], str):
                        raise ValueError("WorkAgent candidates may edit only skill.json instructions")
                    self.skill_model.model_validate({**champion_package, **payload})
            except (ValueError, TypeError) as exc:
                result = {"status": "completed", "candidate_status": "invalid_patch", "reason": str(exc),
                          "champion_before": champion.model_dump(mode="json"), "champion_after": champion.model_dump(mode="json"),
                          "baseline": baseline, "candidate": candidate.model_dump(mode="json"),
                          "actual_edit_count": len(candidate.atomic_edits)}
                self._write_round_summary(root, result)
                return result

        patch_hash = canonical_json_hash([edit.model_dump(mode="json") for edit in candidate.atomic_edits])
        if self.registry.has_negative_evidence(skill_id=skill_id, candidate_id=candidate.candidate_id, patch_hash=patch_hash):
            result = {
                "status": "completed",
                "round_index": round_index,
                "candidate_status": "pruned_negative_evidence",
                "champion_before": champion.model_dump(mode="json"),
                "champion_after": champion.model_dump(mode="json"),
                "rollback_point": rollback_point,
                "inherited_evidence_refs": list(inherited_evidence_refs or []),
                "edit_budget": edit_budget,
                "actual_edit_count": len(candidate.atomic_edits),
                "candidate": candidate.model_dump(mode="json"),
                "candidate_diff": {"patch_hash": patch_hash, "edits": [edit.model_dump(mode="json") for edit in candidate.atomic_edits]},
                "provider_record": provider_record.model_dump(mode="json"),
                "baseline": baseline,
                "candidate_reports": {},
                "negative_evidence": {"candidate_id": candidate.candidate_id, "patch_hash": patch_hash, "reason": "identical candidate was previously rejected"},
                "decision": {"decision": "pruned", "evidence_refs": list(inherited_evidence_refs or [])},
            }
            self._write_round_summary(root, result)
            return result

        verification = self.verifier.verify(candidate, workspace, verification_policy)
        if verification.passed:
            candidate_package = dict(champion_package)
            for edit in candidate.atomic_edits:
                candidate_package.update(json.loads(edit.patch))
            candidate_config = self.skill_model.model_validate(candidate_package)
            candidate_reports = self._evaluate_all(tasks_by_split, candidate_config, contract, root / "candidate")
            if self._is_workagent and self._incomplete(candidate_reports, tasks_by_split):
                result = {"status": "incomplete", "round_index": round_index,
                          "champion_before": champion.model_dump(mode="json"), "champion_after": champion.model_dump(mode="json"),
                          "rollback_point": rollback_point, "baseline": baseline, "candidate_reports": candidate_reports,
                          "candidate": candidate.model_dump(mode="json"), "verification": verification.model_dump(mode="json"),
                          "actual_edit_count": len(candidate.atomic_edits)}
                self._write_round_summary(root, result)
                return result
        else:
            candidate_package = dict(champion_package)
            candidate_reports = {}
        metrics = self._metrics(baseline, candidate_reports, verification.passed)
        if self._is_workagent:
            metrics["critical_regressions"] = self.evaluator.critical_regressions(
                root / "baseline" / "regression", root / "candidate" / "regression"
            ) if candidate_reports else baseline.get("regression", {}).get("success_count", 0)
            baseline_time = sum(report["completed_wall_time_seconds"] for report in baseline.values())
            candidate_time = sum(report["completed_wall_time_seconds"] for report in candidate_reports.values()) if candidate_reports else baseline_time
            if candidate_reports and baseline_time:
                metrics["cost_delta"] = (candidate_time - baseline_time) / baseline_time
            else:
                metrics.pop("cost_delta")
        decision = self.promotion.decide(candidate.candidate_id, verification, metrics, contract)
        version = self.registry.next_version(skill_id, champion.version)
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
        negative_evidence = None
        if decision.decision != "accept":
            negative_id = self.registry.record_negative_evidence(
                skill_id=skill_id,
                candidate_id=candidate.candidate_id,
                parent_version=champion.version,
                patch_hash=patch_hash,
                reason=decision.decision,
                evidence_refs=decision.evidence_refs,
            )
            negative_evidence = {
                "evidence_id": negative_id,
                "candidate_id": candidate.candidate_id,
                "patch_hash": patch_hash,
                "reason": decision.decision,
            }
        if decision.decision == "accept":
            self.registry.set_champion(skill_id, record.version, decision.evidence_refs)
        champion_after = self.registry.champion(skill_id)
        result = {
            "status": "completed",
            "round_index": round_index,
            "champion_before": champion.model_dump(mode="json"),
            "champion_after": champion_after.model_dump(mode="json"),
            "rollback_point": rollback_point,
            "inherited_evidence_refs": list(inherited_evidence_refs or []),
            "candidate": candidate.model_dump(mode="json"),
            "candidate_diff": {"patch_hash": patch_hash, "edits": [edit.model_dump(mode="json") for edit in candidate.atomic_edits]},
            "provider_record": provider_record.model_dump(mode="json"),
            "verification": verification.model_dump(mode="json"),
            "baseline": baseline,
            "candidate_reports": candidate_reports,
            "metrics": metrics,
            "decision": decision.model_dump(mode="json"),
            "registered_version": record.model_dump(mode="json"),
            "negative_evidence": negative_evidence,
            "edit_budget": edit_budget,
            "actual_edit_count": len(candidate.atomic_edits),
        }
        self._write_round_summary(root, result)
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
                reveal_per_task=split == "develop" if self._is_workagent else split != "hidden",
            )
        return reports

    @property
    def _is_workagent(self) -> bool:
        return issubclass(self.skill_model, WorkAgentSkill)

    @staticmethod
    def _incomplete(reports: dict[str, dict], tasks_by_split: dict[str, Sequence[TaskSpec]]) -> bool:
        return any(tasks and (split not in reports or reports[split].get("status") != "completed" or "score" not in reports[split])
                   for split, tasks in tasks_by_split.items())

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

    @staticmethod
    def _write_round_summary(root: Path, result: dict) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "round_summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _identity(self, contract: EvaluationContract, tasks_by_split: dict[str, Sequence[TaskSpec]], model_identity: str | None) -> dict:
        split_hashes = {
            split: canonical_json_hash([task.model_dump(mode="json") for task in tasks])
            for split, tasks in tasks_by_split.items()
            if tasks
        }
        return {
            "contract_hash": canonical_json_hash(contract.model_dump(mode="json")),
            "dataset_hash": contract.dataset_hash,
            "split_hashes": split_hashes,
            "evaluator_hash": self.evaluator.evaluator_hash,
            "provider_identity": {
                "class": f"{self.provider.__class__.__module__}.{self.provider.__class__.__qualname__}",
                "version": str(getattr(self.provider, "provider_version", "unknown")),
            },
            "model_identity": model_identity or getattr(self.provider, "model_identity", None),
            "code_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }

    def _materialize_source_snapshot(self, skill_id: str, root: Path, round_number: int, attempt: int) -> Path:
        """Expose only the current champion package to the next candidate."""

        champion = self.registry.champion(skill_id)
        snapshot_name = f"round-{round_number:02d}" if attempt == 1 else f"round-{round_number:02d}-retry-{attempt:02d}"
        snapshot = root / "source_snapshots" / snapshot_name
        snapshot.mkdir(parents=True, exist_ok=True)
        (snapshot / "skill.json").write_text(json.dumps(self.registry.package(champion), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return snapshot

    @staticmethod
    def _validate_task_splits(tasks_by_split: dict[str, Sequence[TaskSpec]], contract: EvaluationContract) -> None:
        observed = {
            split: canonical_json_hash([task.model_dump(mode="json") for task in tasks])
            for split, tasks in tasks_by_split.items()
            if tasks
        }
        for split, fingerprint in observed.items():
            if contract.split_hashes.get(split) != fingerprint:
                raise ValueError(f"split hash does not match contract: {split}")
        if canonical_json_hash(observed) != contract.dataset_hash:
            raise ValueError("dataset hash does not match contract")

    @staticmethod
    def _validate_checkpoint(checkpoint: dict, identity: dict) -> None:
        for key in ("contract_hash", "dataset_hash", "evaluator_hash", "provider_identity", "model_identity", "code_hash"):
            if checkpoint.get(key) != identity.get(key):
                raise ValueError(f"{key} identity does not match checkpoint")
        if checkpoint.get("split_hashes") != identity.get("split_hashes"):
            raise ValueError("dataset split identity does not match checkpoint")

    @staticmethod
    def _write_checkpoint(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _inherited_evidence(rounds_data: list[dict]) -> list[str]:
        if not rounds_data:
            return []
        latest = rounds_data[-1]
        champion = latest.get("champion_after", {})
        return list(champion.get("evidence_refs", [])) or list(latest.get("inherited_evidence_refs", []))

    @staticmethod
    def _summary(identity: dict, rounds_data: list[dict], root: Path, *, status: str) -> dict:
        first_baseline = rounds_data[0].get("baseline", {}) if rounds_data else {}
        last_round = rounds_data[-1] if rounds_data else {}
        final_reports = last_round.get("candidate_reports") or last_round.get("baseline", {})
        accepted = sum(1 for row in rounds_data if row.get("decision", {}).get("decision") == "accept")
        rejected = sum(1 for row in rounds_data if row.get("decision", {}).get("decision") == "reject")
        pruned = sum(1 for row in rounds_data if row.get("candidate_status") == "pruned_negative_evidence")
        metrics = {
            "accepted_rounds": float(accepted),
            "rejected_rounds": float(rejected),
            "pruned_rounds": float(pruned),
            "completed_rounds": float(len(rounds_data)),
        }
        if first_baseline.get("develop", {}).get("score") is not None:
            metrics["initial_develop_score"] = float(first_baseline["develop"]["score"])
        if final_reports.get("develop", {}).get("score") is not None:
            metrics["final_develop_score"] = float(final_reports["develop"]["score"])
        return {
            "status": status,
            "round_count": len(rounds_data),
            "rounds": rounds_data,
            "checkpoint": str((root / "checkpoint.json").resolve()),
            "identity": identity,
            "champion_version": (rounds_data[-1].get("champion_after", {}).get("version") if rounds_data else None),
            "metrics": metrics,
        }
