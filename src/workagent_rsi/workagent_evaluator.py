"""Frozen RSI evaluation through the shared Office evaluator and verifier."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Sequence

from .artifact_assessment import spec_from_task
from .contracts import TaskSpec
from .harness import Harness
from .hashing import canonical_json_hash, sha256_file
from .path_safety import validated_task_directory
from .rsi_contracts import EvaluationContract
from .workagent_provider import WorkAgentConfig, WorkAgentSkill


class WorkAgentFrozenEvaluator:
    """Run fixed WorkAgent tasks and persist the remote score and issue reports."""

    VERSION = "workagent-artifact-evaluator-v1"

    def __init__(
        self,
        *,
        workagent_config: WorkAgentConfig | None = None,
        input_base: str | Path | None = None,
        assessment_config=None,
        assessment=None,
        assessment_output_root: str | Path | None = None,
    ) -> None:
        self.workagent_config = workagent_config or WorkAgentConfig()
        self.input_base = Path(input_base) if input_base is not None else Path.cwd()
        if assessment is None:
            from .model_judgement import configured_assessment

            output_root = Path(
                assessment_output_root
                or Path.cwd() / "project_artifacts" / "results" / "workagent_model_evidence"
            )
            assessment = configured_assessment(assessment_config or {}, output_root)
        self.assessment = assessment
        self.assessment_identity = self.assessment.identity()
        self.evaluator_hash = self._identity(self.assessment_identity)
        self._task_outcomes: dict[Path, dict[str, bool]] = {}

    def critical_regressions(self, baseline_root: Path, candidate_root: Path) -> int:
        baseline = self._task_outcomes[baseline_root.resolve()]
        candidate = self._task_outcomes[candidate_root.resolve()]
        if baseline.keys() != candidate.keys():
            raise ValueError("regression task evidence does not match frozen split")
        return sum(passed and not candidate[task_id] for task_id, passed in baseline.items())

    def evaluate_split(
        self,
        tasks: Sequence[TaskSpec],
        split_name: str,
        config: WorkAgentSkill,
        contract: EvaluationContract,
        result_root: str | Path,
        *,
        reveal_per_task: bool = False,
    ) -> dict:
        split_hash = canonical_json_hash([task.model_dump(mode="json") for task in tasks])
        if contract.split_hashes.get(split_name) != split_hash:
            raise ValueError("split hash does not match frozen evaluation contract")
        live_evaluator_hash = self._identity(self.assessment.identity())
        if contract.evaluator_hash != self.evaluator_hash or self.evaluator_hash != live_evaluator_hash:
            raise ValueError("evaluator identity does not match frozen evaluation contract")
        if contract.assessment_mode != "artifact-v1":
            raise ValueError("WorkAgent frozen evaluation requires artifact-v1 assessment mode")
        if contract.assessment_identity != self.assessment_identity:
            raise ValueError("artifact assessment identity does not match contract")
        provider_policy = "workagent-config:" + canonical_json_hash(
            self.workagent_config.model_dump(mode="json")
        )
        if contract.provider_policy != provider_policy:
            raise ValueError("WorkAgent provider configuration does not match contract")
        specs = {task.task_id: spec_from_task(task) for task in tasks}
        for task_id, spec in specs.items():
            if contract.acceptance_hashes.get(task_id) != spec.fingerprint():
                raise ValueError("acceptance specification does not match frozen contract")

        root = Path(result_root)
        root.mkdir(parents=True, exist_ok=True)
        rows: list[dict] = []
        repeat_agreement: list[bool] = []
        completed_seconds = 0.0
        for task in tasks:
            task_root = validated_task_directory(root, task.task_id)
            repeated: list[dict] = []
            for repeat in range(contract.repeats):
                attempt_root = task_root / f"repeat-{repeat + 1}"
                harness = Harness(
                    attempt_root,
                    execution_provider="workagent",
                    workagent_config=self.workagent_config,
                    agent_instructions=config.instructions,
                    input_base=self.input_base,
                    assessment=self.assessment,
                )
                started = time.perf_counter()
                result = harness.run(task, run_id="run")
                elapsed = time.perf_counter() - started
                repeated.append(
                    self._evaluation_row(
                        task,
                        result,
                        attempt_root,
                        specs[task.task_id],
                        elapsed,
                    )
                )

            model_requirements = {
                requirement.requirement_id
                for requirement in specs[task.task_id].requirements
                if requirement.check in {"semantic", "visual"}
            }
            model_used = any(
                row["telemetry"].get(channel)
                for row in repeated
                for channel in ("visual", "semantic")
            )
            independent = not model_used or all(
                item.get("model_calls", 0) > 0
                for row in repeated
                for channel in ("visual", "semantic")
                for item in row["telemetry"].get(channel, [])
            )
            agreement = len(repeated) >= 2 and independent and all(
                self._signature(row, model_requirements) == self._signature(repeated[0], model_requirements)
                for row in repeated[1:]
            )
            repeat_agreement.append(agreement)
            rows.append(
                {
                    **repeated[0],
                    "repeat_count": len(repeated),
                    "repeat_agreement": agreement,
                }
            )
            completed_seconds += sum(
                row["wall_time_seconds"]
                for row in repeated
                if row.get("assessment_complete") and "score" in row
            )

        complete = bool(rows) and len(rows) == len(tasks) and all(
            row.get("assessment_complete") and "score" in row for row in rows
        )
        quality = (
            sum(row["score"] for row in rows) / len(rows)
            if complete
            else None
        )
        dimensions = sorted(
            {
                name
                for row in rows
                for name in (row.get("score_report") or {}).get("dimension_scores", {})
            }
        )
        dimension_scores = {}
        for dimension in dimensions:
            values = [
                (row.get("score_report") or {}).get("dimension_scores", {}).get(dimension)
                for row in rows
                if row.get("score_report") is not None
            ]
            dimension_scores[dimension] = (
                None
                if not values or any(value is None for value in values)
                else sum(values) / len(values) / 100
            )
        report = {
            "split": split_name,
            "status": "completed" if complete else "incomplete",
            "task_count": len(rows),
            "completed_count": sum("score" in row for row in rows),
            "success_count": sum(bool(row.get("passed")) for row in rows),
            "success_rate": sum(bool(row.get("passed")) for row in rows) / len(rows) if complete else None,
            "score": quality,
            "quality_score": quality,
            "dimension_scores": dimension_scores,
            "coverage": sum(row.get("coverage", 0) for row in rows) / len(rows) if rows else 0,
            "assessment_complete": complete,
            "repeat_agreement": bool(rows) and all(repeat_agreement),
            "evaluation_seconds": completed_seconds,
            "assessment_mode": "artifact-v1",
            "assessment_identity": self.assessment_identity,
            "evaluator_hash": live_evaluator_hash,
            "split_hash": split_hash,
            "rows": rows,
        }
        (root / "evaluation_full.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        public = {key: value for key, value in report.items() if key != "rows"}
        if reveal_per_task and split_name != "hidden":
            public["rows"] = [row for row in rows if not row["hidden_test"]]
        (root / "evaluation_public.json").write_text(
            json.dumps(public, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if complete:
            self._task_outcomes[root.resolve()] = {
                row["task_id"]: row["passed"] for row in rows
            }
        return public

    def _evaluation_row(
        self,
        task: TaskSpec,
        result: dict,
        attempt_root: Path,
        spec,
        elapsed: float,
    ) -> dict:
        evaluation = result.get("evaluation") or {}
        report_paths = evaluation.get("report_paths") or {}
        score_report = self._read_report(report_paths.get("score"), attempt_root)
        issue_report = self._read_report(report_paths.get("issues"), attempt_root)
        assessment_report = self._read_report(report_paths.get("assessment"), attempt_root)
        reports_share_snapshot = bool(score_report and issue_report and assessment_report) and (
            score_report.get("evaluator_identity")
            == issue_report.get("evaluator_identity")
            == assessment_report.get("evaluator_identity")
            == self.assessment_identity
            and score_report.get("spec_hash")
            == issue_report.get("spec_hash")
            == assessment_report.get("spec_hash")
            == spec.fingerprint()
            and score_report.get("artifact_hashes")
            == issue_report.get("artifact_hashes")
            == assessment_report.get("artifact_hashes")
        )
        score_100 = (score_report or {}).get("total_score")
        score = None
        if isinstance(score_100, (int, float)) and not isinstance(score_100, bool):
            value = float(score_100)
            if math.isfinite(value) and 0 <= value <= 100:
                score = value / 100
        check_statuses = [
            item.get("status")
            for item in (score_report or {}).get("criterion_results", [])
        ]
        com_reopen = result.get("com_reopen")
        com_required = (
            self.workagent_config.verify_com
            and (score_report or {}).get("acceptance_status") == "PASS"
        )
        com_check_complete = (
            not com_required
            or (
                isinstance(com_reopen, dict)
                and com_reopen.get("ok") is True
                and com_reopen.get("status") == "available"
            )
        )
        assessment_complete = (
            result.get("state") in {"SUCCEEDED", "FAILED"}
            and reports_share_snapshot
            and score is not None
            and (score_report or {}).get("acceptance_status") in {"PASS", "FAIL"}
            and bool(check_statuses)
            and all(
                status in {"PASS", "PARTIAL", "FAIL", "NOT_APPLICABLE"}
                for status in check_statuses
            )
            and com_check_complete
        )
        compatibility_score = evaluation.get("score")
        if assessment_complete and (
            not isinstance(compatibility_score, (int, float))
            or isinstance(compatibility_score, bool)
            or abs(float(compatibility_score) - score) > 1e-8
        ):
            assessment_complete = False
            score = None

        row = {
            "task_id": task.task_id,
            "domain": task.domain,
            "hidden_test": task.hidden_test,
            "state": result.get("state"),
            "result_dir": result.get("result_dir", str(attempt_root.resolve())),
            "assessment_identity": (score_report or {}).get("evaluator_identity"),
            "assessment_complete": assessment_complete,
            "com_reopen": com_reopen,
            "score_report": score_report,
            "issue_report": issue_report,
            "critical_requirements": [
                requirement.requirement_id
                for requirement in spec.requirements
                if requirement.critical and requirement.applicable
            ],
            "critical_failures": evaluation.get("critical_failures", []),
            "failure": result.get("failure"),
            "evidence_path": str((attempt_root / "assessment").resolve()),
            "telemetry": (assessment_report or {}).get("telemetry", {}),
            "coverage": (score_report or {}).get("coverage", {}).get("ratio", 0),
            "wall_time_seconds": round(elapsed, 6),
        }
        if assessment_complete and score is not None:
            row.update(
                passed=bool(evaluation.get("passed")) and result.get("state") == "SUCCEEDED",
                score=score,
                quality_score=score,
            )
        else:
            row["status"] = "incomplete"
            if not row["failure"]:
                row["failure"] = "missing, incomplete, or inconsistent artifact assessment"
        return row

    @staticmethod
    def _read_report(value: str | None, attempt_root: Path) -> dict | None:
        if not value:
            return None
        path = Path(value).resolve()
        if not path.is_relative_to(attempt_root.resolve()) or not path.is_file():
            raise ValueError("assessment report path is missing or outside the run directory")
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _signature(row: dict, model_requirements: set[str]) -> dict:
        score_report = row.get("score_report") or {}
        return {
            "score": row.get("score"),
            "passed": row.get("passed"),
            "checks": [
                (
                    check.get("requirement_id"),
                    check.get("status"),
                    check.get("completion")
                    if check.get("requirement_id") in model_requirements
                    else check.get("observed"),
                )
                for check in score_report.get("criterion_results", [])
            ],
        }

    @classmethod
    def _identity(cls, assessment_identity: str) -> str:
        package = Path(__file__).resolve().parent
        names = (
            "workagent_evaluator.py",
            "harness_artifact_evaluator.py",
            "harness.py",
            "run.py",
            "orchestrator.py",
            "contracts.py",
            "artifact_com.py",
            "workagent_office.py",
            "workagent_provider.py",
            "prompts/office_agent.md",
            "schemas/agent_response.schema.json",
        )
        files = {name: sha256_file(package / name) for name in names}
        return canonical_json_hash(
            {
                "version": cls.VERSION,
                "files": files,
                "assessment_identity": assessment_identity,
            }
        )
