"""Immutable WorkAgent RSI experiment setup."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from contextlib import nullcontext
from typing import Sequence

from .artifact_assessment import spec_from_task
from .candidate_provider import CandidateProvider
from .candidate_workspace import CandidateWorkspaceBuilder
from .contracts import TaskSpec
from .hashing import canonical_json_hash
from .promotion import PromotionController
from .registry import SkillRegistry
from .rsi_contracts import EvaluationContract
from .rsi_loop import RSILoop
from .verifier import CandidateVerifier, VerificationPolicy
from .workagent_evaluator import WorkAgentFrozenEvaluator
from .workagent_provider import WorkAgentConfig, WorkAgentSkill


class WorkAgentExperimentRunner:
    def __init__(
        self,
        *,
        workagent_config: WorkAgentConfig | None = None,
        input_base: str | Path | None = None,
        assessment_config=None,
        repair_policy=None,
        run_budget=None,
    ) -> None:
        self.repair_policy=repair_policy
        self.run_budget=run_budget
        self.workagent_config = workagent_config
        self.input_base = input_base
        self.assessment_config = assessment_config

    def run(
        self,
        tasks_by_split: dict[str, Sequence[TaskSpec]],
        initial_skill: WorkAgentSkill,
        provider: CandidateProvider,
        output_root: str | Path,
        *,
        rounds: int = 1,
    ) -> dict:
        from .repair_loop import RunBudget, RepairPolicy
        if self.repair_policy is not None and self.run_budget is None:
            policy=RepairPolicy.model_validate(self.repair_policy)
            self.run_budget=RunBudget(max_repairs=policy.max_repairs,max_wall_seconds=policy.total_deadline_seconds)
        context=self.run_budget.activate(Path(output_root)/'budget-ledger.json') if self.run_budget else nullcontext()
        # Preserve the existing nonempty-root guard before creating the ledger.
        if Path(output_root).exists() and any(Path(output_root).iterdir()):
            raise FileExistsError(output_root)
        with context:
            return self._run(tasks_by_split,initial_skill,provider,output_root,rounds=rounds)

    def _run(self,tasks_by_split,initial_skill,provider,output_root,*,rounds):
        required = {"develop", "regression", "hidden", "ood_transfer"}
        if set(tasks_by_split) != required or any(not tasks_by_split[split] for split in required):
            raise ValueError("WorkAgent RSI requires nonempty develop, regression, hidden, and ood_transfer splits")
        root = Path(output_root)
        root.mkdir(parents=True, exist_ok=True)
        workagent_config = self.workagent_config or WorkAgentConfig()
        evaluator = WorkAgentFrozenEvaluator(
            workagent_config=workagent_config,
            input_base=self.input_base,
            assessment_config=self.assessment_config,
            assessment_output_root=root / "model_evidence",
            repair_policy=self.repair_policy,
            run_budget=self.run_budget,
        )
        split_hashes = {split: canonical_json_hash([task.model_dump(mode="json") for task in tasks])
                        for split, tasks in tasks_by_split.items()}
        acceptance_hashes = {}
        for task_rows in tasks_by_split.values():
            for task in task_rows:
                fingerprint = spec_from_task(task).fingerprint()
                previous = acceptance_hashes.setdefault(task.task_id, fingerprint)
                if previous != fingerprint:
                    raise ValueError("a task ID maps to different acceptance specifications")
        task_count = sum(len(tasks) for tasks in tasks_by_split.values())
        evaluation_budget = max(1, task_count) * workagent_config.timeout_seconds * 2 * 4
        try:
            git_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2], text=True
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            git_commit = "unavailable"
        contract = EvaluationContract(
            contract_id="general-office-rsi-v1",
            dataset_hash=canonical_json_hash(split_hashes),
            split_hashes=split_hashes,
            evaluator_hash=evaluator.evaluator_hash,
            provider_policy="workagent-config:" + canonical_json_hash(workagent_config.model_dump(mode="json")),
            seeds=[20260930], repeats=2, timeout_seconds=workagent_config.timeout_seconds,
            thresholds={
                "quality_gain": 0.05,
                "success_tolerance": 0.01,
                "protected_quality_tolerance": 0.01,
                "max_evaluation_seconds": float(evaluation_budget),
            },
            git_commit=git_commit,
            assessment_mode="artifact-v1",
            assessment_identity=evaluator.assessment_identity,
            acceptance_hashes=acceptance_hashes,
        )
        if self.run_budget is not None:
            (root/'budget-policy.json').write_text(json.dumps(self.run_budget.limits.model_dump(mode='json'),indent=2)+'\n',encoding='utf-8')
        (root / "contract.json").write_text(json.dumps(contract.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        registry = SkillRegistry(root / "registry")
        champion = registry.register(
            skill_id="office.workagent", version=initial_skill.version, package=initial_skill.model_dump(),
            manifest={"domain": "office", "provider": "workagent"}, parent_version=None,
            candidate_id=None, status="champion", evidence_refs=[contract.dataset_hash],
        )
        source = root / "source"
        source.mkdir()
        (source / "skill.json").write_text(json.dumps(initial_skill.model_dump(), indent=2) + "\n", encoding="utf-8")
        loop = RSILoop(
            registry=registry, workspace_builder=CandidateWorkspaceBuilder(), provider=provider,
            verifier=CandidateVerifier(), evaluator=evaluator,
            promotion=PromotionController(), skill_model=WorkAgentSkill,
        )
        summary = loop.run(
            skill_id=champion.skill_id, tasks_by_split=tasks_by_split, contract=contract,
            source_root=source, run_root=root / "rounds",
            verification_policy=VerificationPolicy(
                allowed_targets={"skill.json"},
                protected_paths={
                    "assessment_contracts.py",
                    "artifact_assessment.py",
                    "artifact_evaluator.py",
                    "artifact_verifier.py",
                    "harness_artifact_evaluator.py",
                    "office_checks.py",
                    "workagent_evaluator.py",
                },
                protected_values=self._protected_values(
                    [
                        task
                        for split in ("regression", "hidden", "ood_transfer")
                        for task in tasks_by_split.get(split, [])
                    ]
                ),
            ),
            rounds=rounds,
        )
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return summary

    @staticmethod
    def _protected_values(tasks: Sequence[TaskSpec]) -> list[str]:
        values: set[str] = set()

        def collect(value) -> None:
            if isinstance(value, str):
                if len(value.strip()) >= 6:
                    values.add(value.strip())
            elif isinstance(value, dict):
                for nested in value.values():
                    collect(nested)
            elif isinstance(value, (list, tuple)):
                for nested in value:
                    collect(nested)

        for task in tasks:
            collect(task.task_id)
            collect(task.instruction)
            collect(task.expected_constraints)
        return sorted(values)
