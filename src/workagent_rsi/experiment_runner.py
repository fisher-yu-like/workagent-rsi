from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .candidate_provider import CandidateProvider
from .candidate_workspace import CandidateWorkspaceBuilder
from .contracts import TaskSpec
from .frozen_evaluator import FrozenEvaluator, ResponseJudge
from .hashing import canonical_json_hash, sha256_file
from .leakage import LeakageCritic
from .promotion import PromotionController
from .registry import SkillRegistry
from .rsi_contracts import AtomicEdit, CandidatePatch, EvaluationContract, ExperimentResult
from .rsi_loop import RSILoop
from .skill_runtime import PilotSkillConfig
from .verifier import CandidateVerifier, VerificationPolicy


class ExperimentRunner:
    def __init__(self, data_root: str | Path, repository_root: str | Path) -> None:
        self.data_root = Path(data_root)
        self.repository_root = Path(repository_root)
        self.evaluator_hash = sha256_file(Path(__file__).with_name("frozen_evaluator.py"))

    def run(
        self,
        experiment_id: str,
        provider: CandidateProvider,
        output_root: str | Path,
        *,
        invocation_id: str | None = None,
    ) -> ExperimentResult:
        if experiment_id not in {f"E{index:02d}" for index in range(1, 13)}:
            raise ValueError(f"unknown experiment: {experiment_id}")
        invocation = invocation_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        root = Path(output_root) / experiment_id / invocation
        if root.exists():
            raise FileExistsError(root)
        root.mkdir(parents=True)
        tasks = self._tasks_for(experiment_id)
        if not tasks.get("develop"):
            fallback = next((items for items in tasks.values() if items), [])
            tasks["develop"] = list(fallback)
        contract = self._contract(experiment_id, tasks)
        (root / "contract.json").write_text(json.dumps(contract.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summary: dict
        status = "completed"
        failure: str | None = None
        try:
            if experiment_id == "E01":
                evaluator = FrozenEvaluator(self.evaluator_hash)
                report = evaluator.evaluate_split(
                    tasks["develop"], "develop", PilotSkillConfig(marker_source="task_id"), contract, root / "baseline"
                )
                summary = {"experiment_id": experiment_id, "arm": "fixed_skill", "metrics": {"task_success_rate": report["score"]}, "report": report}
            elif experiment_id == "E07":
                audit_tasks = list(tasks.get("develop", [])) + list(tasks.get("regression", [])) + list(tasks.get("ood_transfer", []))
                audit_tasks = list({task.task_id: task for task in audit_tasks}.values())
                audit_hash = canonical_json_hash([task.model_dump(mode="json") for task in audit_tasks])
                audit_contract = contract.model_copy(update={"split_hashes": {"automated_audit": audit_hash}})
                artifact = FrozenEvaluator(self.evaluator_hash).evaluate_split(
                    audit_tasks,
                    "automated_audit",
                    PilotSkillConfig(marker_source="task_id"),
                    audit_contract,
                    root / "artifact_channel",
                )
                response = ResponseJudge().evaluate(audit_tasks, PilotSkillConfig(marker_source="task_id"))
                comparison = ResponseJudge.agreement(artifact, response)
                summary = {
                    "experiment_id": experiment_id,
                    "arm": "automated_cross_evaluation",
                    "metrics": {"agreement_rate": comparison["agreement_rate"], "comparison_label": comparison["label"]},
                    "artifact_report": artifact,
                    "response_report": response,
                    "comparison": comparison,
                }
            elif experiment_id == "E11":
                adversarial = CandidatePatch(
                    candidate_id="adversarial-leakage-fixture",
                    parent_version="0.1.0",
                    provider="fixture",
                    provider_version="1",
                    diagnosis_refs=["a" * 64],
                    atomic_edits=[
                        AtomicEdit(
                            component="prompt",
                            target_path="skill.json",
                            hypothesis="memorize task",
                            expected_metric="develop_score",
                            patch='{"p3-task-001":"answer"}',
                        )
                    ],
                    edit_budget=1,
                    created_at=datetime.now(timezone.utc),
                )
                findings = LeakageCritic().scan(adversarial)
                hidden_report = {}
                if tasks.get("hidden"):
                    hidden_report = FrozenEvaluator(self.evaluator_hash).evaluate_split(
                        tasks["hidden"], "hidden", PilotSkillConfig(marker_source="task_id"), contract, root / "hidden", reveal_per_task=False
                    )
                summary = {
                    "experiment_id": experiment_id,
                    "arm": "leakage_critic_ablation",
                    "metrics": {"critic_enabled_rejection_rate": 1.0 if findings else 0.0, "critic_disabled_rejection_rate": 0.0},
                    "findings": findings,
                    "hidden_aggregate": hidden_report,
                }
            else:
                registry = SkillRegistry(root / "registry")
                baseline = registry.register(
                    skill_id="office.marker",
                    version="0.1.0",
                    package={"marker_source": "task_id"},
                    manifest={"domain": "office"},
                    parent_version=None,
                    candidate_id=None,
                    status="champion",
                    evidence_refs=[contract.dataset_hash],
                )
                source = root / "source"
                source.mkdir()
                (source / "skill.json").write_text(json.dumps({"marker_source": "task_id"}) + "\n", encoding="utf-8")
                loop = RSILoop(
                    registry=registry,
                    workspace_builder=CandidateWorkspaceBuilder(),
                    provider=provider,
                    verifier=CandidateVerifier(),
                    evaluator=FrozenEvaluator(self.evaluator_hash),
                    promotion=PromotionController(),
                )
                round_result = loop.run_round(
                    skill_id=baseline.skill_id,
                    tasks_by_split=tasks,
                    contract=contract,
                    source_root=source,
                    run_root=root / "round",
                    verification_policy=VerificationPolicy(
                        allowed_targets={"skill.json"},
                        protected_paths={"evaluator.py", "frozen_evaluator.py", "promotion.py", "hidden.jsonl"},
                    ),
                )
                if round_result.get("status") in {"unavailable", "timeout"}:
                    status = "unavailable"
                    failure = str(round_result.get("provider_record", {}).get("error"))
                elif round_result.get("status") == "failed":
                    status = "failed"
                    failure = str(round_result.get("provider_record", {}).get("error"))
                comparison_metrics = self._comparison_metrics(experiment_id, round_result)
                summary = {
                    "experiment_id": experiment_id,
                    "arm": self._arm(experiment_id),
                    "round": round_result,
                    "metrics": {**round_result.get("metrics", {}), **comparison_metrics},
                }
                if comparison_metrics:
                    summary["comparison_mode"] = "paired_candidate_policy_replay"
        except Exception as exc:
            status = "failed"
            failure = str(exc)
            summary = {"experiment_id": experiment_id, "metrics": {}, "failure": failure}
        evidence_hash = canonical_json_hash(summary)
        public_summary = {
            **summary,
            "status": status,
            "contract_hash": canonical_json_hash(contract.model_dump(mode="json")),
            "evidence_refs": [evidence_hash],
            "failure": failure,
        }
        (root / "summary.json").write_text(json.dumps(public_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        numeric_metrics = {key: float(value) for key, value in summary.get("metrics", {}).items() if isinstance(value, (int, float))}
        return ExperimentResult(
            experiment_id=experiment_id,
            invocation_id=invocation,
            status=status,
            contract_hash=public_summary["contract_hash"],
            metrics=numeric_metrics,
            evidence_refs=[evidence_hash],
            failure=failure,
        )

    def _contract(self, experiment_id: str, tasks: dict[str, Sequence[TaskSpec]]) -> EvaluationContract:
        split_hashes = {
            split: canonical_json_hash([task.model_dump(mode="json") for task in rows])
            for split, rows in tasks.items()
            if rows
        }
        dataset_hash = canonical_json_hash(split_hashes)
        try:
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.repository_root, text=True).strip()
        except Exception:
            commit = "unavailable"
        return EvaluationContract(
            contract_id=f"{experiment_id}-pilot-v1",
            dataset_hash=dataset_hash,
            split_hashes=split_hashes,
            evaluator_hash=self.evaluator_hash,
            provider_policy="codex-backed-local-or-declared-test-provider",
            seeds=[20260924],
            repeats=1,
            timeout_seconds=180,
            thresholds={
                "develop_gain": 0.05,
                "regression_tolerance": 0.01,
                "hidden_degradation": 0.01,
                "ood_degradation": 0.01,
                "max_cost_delta": 1.0,
            },
            git_commit=commit,
        )

    def _tasks_for(self, experiment_id: str) -> dict[str, list[TaskSpec]]:
        paths = {
            "evolve": self.data_root / "splits" / "evolve.jsonl",
            "develop": self.data_root / "splits" / "develop.jsonl",
            "regression": self.data_root / "splits" / "regression.jsonl",
            "hidden": self.data_root / "protected" / "hidden.jsonl",
            "ood_transfer": self.data_root / "splits" / "ood_transfer.jsonl",
        }
        if experiment_id in {"E07", "E08"}:
            domains = {"excel", "word", "powerpoint"}
        elif experiment_id == "E12":
            domains = {"word", "powerpoint"}
        else:
            domains = {"excel"}
        return {split: [task for task in self._load(path) if task.domain.lower() in domains] for split, path in paths.items()}

    @staticmethod
    def _load(path: Path) -> list[TaskSpec]:
        if not path.exists():
            return []
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [
            TaskSpec(
                task_id=row["task_id"],
                domain=row["domain"],
                instruction=row["instruction"],
                input_files=tuple(row.get("input_files", [])),
                expected_constraints=row.get("expected_constraints", {}),
                risk_level=row.get("risk_level", "low"),
                hidden_test=bool(row.get("hidden_test", split_hidden(row.get("split")))),
            )
            for row in rows
        ]

    @staticmethod
    def _comparison_metrics(experiment_id: str, result: dict) -> dict[str, float]:
        candidate_exists = 1.0 if result.get("candidate") else 0.0
        verification_passed = 1.0 if result.get("verification", {}).get("passed") else 0.0
        decision_accept = 1.0 if result.get("decision", {}).get("decision") == "accept" else 0.0
        metrics = result.get("metrics", {})
        develop_only = 1.0 if float(metrics.get("candidate_develop", 0.0)) > float(metrics.get("champion_develop", 0.0)) else 0.0
        if experiment_id == "E03":
            return {
                "generator_only_accept_rate": candidate_exists,
                "verified_accept_rate": verification_passed,
                "invalid_promotion_rate": max(0.0, candidate_exists - verification_passed),
            }
        if experiment_id == "E04":
            return {
                "develop_only_accept_rate": develop_only,
                "modular_accept_rate": decision_accept,
                "invalid_promotion_rate": max(0.0, develop_only - decision_accept),
            }
        if experiment_id == "E06":
            return {
                "verifier_enabled_pass_rate": verification_passed,
                "verifier_disabled_accept_rate": candidate_exists,
                "verifier_prevented_acceptance_rate": max(0.0, candidate_exists - verification_passed),
            }
        if experiment_id == "E08":
            shared = float(result.get("candidate_reports", {}).get("ood_transfer", {}).get("score", 0.0))
            domain_specific = float(result.get("baseline", {}).get("ood_transfer", {}).get("score", 0.0))
            return {"shared_ood_score": shared, "domain_specific_ood_score": domain_specific, "transfer_delta": shared - domain_specific}
        if experiment_id == "E09":
            edits = float(len(result.get("candidate", {}).get("atomic_edits", [])))
            budget = float(result.get("candidate", {}).get("edit_budget", 0))
            return {
                "proposal_regularized_admissible": 1.0 if edits <= budget and budget > 0 else 0.0,
                "proposal_unregularized_admissible": candidate_exists,
                "proposal_edit_count": edits,
            }
        if experiment_id == "E10":
            return {
                "selection_regularized_accept_rate": decision_accept,
                "selection_unregularized_accept_rate": develop_only,
                "selection_prevented_acceptance_rate": max(0.0, develop_only - decision_accept),
            }
        return {}

    @staticmethod
    def _arm(experiment_id: str) -> str:
        return {
            "E02": "self_refine",
            "E03": "generator_plus_verifier",
            "E04": "modular_frozen_evaluator",
            "E05": "full_rsi",
            "E06": "verifier_ablation",
            "E08": "cross_domain_transfer",
            "E09": "proposal_regularization",
            "E10": "selection_regularization",
            "E12": "word_powerpoint_full_rsi",
        }.get(experiment_id, "candidate_loop")


def split_hidden(value: object) -> bool:
    return str(value).lower() == "hidden"
