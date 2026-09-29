"""Immutable WorkAgent RSI experiment setup."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Sequence

from .candidate_provider import CandidateProvider
from .candidate_workspace import CandidateWorkspaceBuilder
from .contracts import TaskSpec
from .evaluator import OfficeArtifactEvaluator
from .hashing import canonical_json_hash
from .promotion import PromotionController
from .registry import SkillRegistry
from .rsi_contracts import EvaluationContract
from .rsi_loop import RSILoop
from .verifier import CandidateVerifier, VerificationPolicy
from .workagent_evaluator import WorkAgentFrozenEvaluator
from .workagent_provider import WorkAgentConfig, WorkAgentSkill


class WorkAgentExperimentRunner:
    def __init__(self, *, workagent_config: WorkAgentConfig | None = None, input_base: str | Path | None = None) -> None:
        self.workagent_config = workagent_config
        self.input_base = input_base

    def run(
        self,
        tasks_by_split: dict[str, Sequence[TaskSpec]],
        initial_skill: WorkAgentSkill,
        provider: CandidateProvider,
        output_root: str | Path,
        *,
        rounds: int = 1,
    ) -> dict:
        required = {"develop", "regression", "hidden", "ood_transfer"}
        if set(tasks_by_split) != required or any(not tasks_by_split[split] for split in required):
            raise ValueError("WorkAgent RSI requires nonempty develop, regression, hidden, and ood_transfer splits")
        root = Path(output_root)
        if root.exists() and any(root.iterdir()):
            raise FileExistsError(root)
        root.mkdir(parents=True, exist_ok=True)
        split_hashes = {split: canonical_json_hash([task.model_dump(mode="json") for task in tasks])
                        for split, tasks in tasks_by_split.items()}
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
            evaluator_hash=OfficeArtifactEvaluator.evaluator_hash(),
            provider_policy="codex-backed-local-or-declared-test-provider",
            seeds=[20260930], repeats=1, timeout_seconds=(self.workagent_config or WorkAgentConfig()).timeout_seconds,
            thresholds={"develop_gain": 0.05, "regression_tolerance": 0.01,
                        "hidden_degradation": 0.01, "ood_degradation": 0.01, "max_cost_delta": 1.0},
            git_commit=git_commit,
        )
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
            verifier=CandidateVerifier(), evaluator=WorkAgentFrozenEvaluator(
                contract.evaluator_hash, workagent_config=self.workagent_config, input_base=self.input_base),
            promotion=PromotionController(), skill_model=WorkAgentSkill,
        )
        summary = loop.run(
            skill_id=champion.skill_id, tasks_by_split=tasks_by_split, contract=contract,
            source_root=source, run_root=root / "rounds",
            verification_policy=VerificationPolicy(allowed_targets={"skill.json"},
                protected_paths={"evaluator.py", "office_checks.py", "render_checks.py", "workagent_evaluator.py"}),
            rounds=rounds,
        )
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return summary
