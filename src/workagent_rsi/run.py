"""Run one task with the normal local adapters."""

from __future__ import annotations

from pathlib import Path
from contextlib import nullcontext
import time
from .hashing import canonical_json_hash

from .contracts import TaskSpec
from .artifact_com import persist_com_result, verify_stored_office_artifacts
from .evaluator import BasicEvaluator
from .harness_artifact_evaluator import HarnessArtifactEvaluator
from .executor import ComOfficeAdapter, LocalOfficeAdapter, MockWorkAgentAdapter, UnavailableOfficeAdapter
from .office_capabilities import CapabilityReport
from .orchestrator import Orchestrator
from .skill_runtime import PilotSkillConfig, SkillConfiguredOfficeAdapter
from .store import Store
from .workagent_office import WorkAgentOfficeAdapter
from .workagent_provider import WorkAgentConfig


OFFICE_DOMAINS = {"excel", "word", "powerpoint"}


class Run:
    """Execute a task once and return its checked result."""

    def __init__(
        self,
        root: str | Path,
        *,
        office: bool | None = None,
        execution_provider: str | None = None,
        capability_report: CapabilityReport | None = None,
        workagent_config: WorkAgentConfig | None = None,
        agent_instructions: str = "",
        input_base: str | Path | None = None,
        model_review_config: dict | None = None,
        assessment=None,
        assessment_profile: str | None = None,
    ) -> None:
        self.root = Path(root)
        self.store = Store(self.root)
        self.office = office
        self.execution_provider = execution_provider
        self.capability_report = capability_report
        self.workagent_config = workagent_config or WorkAgentConfig()
        self.agent_instructions = agent_instructions
        self.input_base = Path(input_base) if input_base is not None else Path.cwd()
        self.model_review_config = model_review_config
        self.assessment = assessment
        self.assessment_profile=assessment_profile

    def execute(self, task: TaskSpec, skill_id: str | None = None, *, max_attempts: int = 1, repair_policy=None,
                run_budget=None, split_name='develop') -> dict:
        from .repair_loop import FeedbackVisibilityPolicy, RepairPolicy, RunBudget
        FeedbackVisibilityPolicy().permits(split_name)
        if repair_policy is not None:
            repair_policy = RepairPolicy.model_validate(repair_policy) if not isinstance(repair_policy, RepairPolicy) else repair_policy
            from .artifact_assessment import spec_from_task
            typed = TaskSpec.model_validate(task) if isinstance(task, dict) else task
            if not set(repair_policy.allowed_artifacts)<=set(spec_from_task(typed).artifacts):
                raise ValueError('allowed_artifacts must name declared task artifacts')
            if run_budget is None:
                run_budget = RunBudget(max_repairs=repair_policy.max_repairs, max_wall_seconds=repair_policy.total_deadline_seconds)
        if run_budget is not None and not isinstance(run_budget, RunBudget):
            raise TypeError('run_budget must be a shared RunBudget instance')
        context = run_budget.activate(self.root/'run-budget.json', wall_seconds=repair_policy.total_deadline_seconds if repair_policy else None) if run_budget else nullcontext()
        with context:
            return self._execute(task, skill_id, max_attempts=max_attempts, repair_policy=repair_policy, split_name=split_name)

    def _execute(self, task, skill_id, *, max_attempts, repair_policy, split_name):
        started=time.monotonic()
        if repair_policy is None:
            return self._execute_once(task, skill_id, max_attempts=max_attempts)
        from .repair_loop import RepairLoop, RepairPolicy, repair_feedback
        if not isinstance(repair_policy, RepairPolicy):
            repair_policy = RepairPolicy.model_validate(repair_policy)
        task = TaskSpec.model_validate(task) if isinstance(task, dict) else task.model_copy(deep=True)
        owners = {}
        initial = self._execute_once(task, skill_id, max_attempts=max_attempts, defer_assessment=True)
        initial_id = initial['run_id']
        owners[initial_id] = self
        def execute_repair(request, root):
            child = Run(root, office=self.office, execution_provider=self.execution_provider,
                capability_report=self.capability_report, workagent_config=self.workagent_config,
                agent_instructions=self.agent_instructions, input_base=self.input_base,
                model_review_config=self.model_review_config, assessment=self.assessment,
                assessment_profile=self.assessment_profile)
            result = child._execute_once(task, skill_id, max_attempts=max_attempts,
                defer_assessment=True, repair_request=request)
            owners[result['run_id']] = child
            return result
        def assess(result):
            return owners[result['run_id']]._assess_execution(task, result)
        result = RepairLoop(self.root/'repair-loop', repair_policy, split_name=split_name, started=started,
                            skill_hash=canonical_json_hash({'instructions':self.agent_instructions})).run(
            task, initial, repair_feedback, execute_repair, assess)
        result['selected_attempt_run_id'] = result['run_id']
        result['run_id'] = initial_id
        self.store.logs.set_state(initial_id, result['state'])
        self.store.logs.append_event(initial_id, 'repair_completed', {
            'repairs':result['repair_loop']['repairs'], 'stop_reason':result['repair_loop']['stop_reason'],
            'selected_attempt_run_id':result['selected_attempt_run_id']})
        return result

    def _execute_once(self, task: TaskSpec, skill_id: str | None = None, *, max_attempts: int = 1,
                      defer_assessment=False, repair_request=None) -> dict:
        if isinstance(task, dict):
            task = TaskSpec.model_validate(task)
        use_office = self.office if self.office is not None else task.domain.lower() in OFFICE_DOMAINS
        provider = self.execution_provider or ("workagent" if use_office else "smoke")
        if provider == "smoke":
            adapter = MockWorkAgentAdapter()
            evaluator = BasicEvaluator()
            default_skill = "task.normal"
        elif provider == "local_office":
            adapter = SkillConfiguredOfficeAdapter(
                self.root / "generated",
                PilotSkillConfig(marker_source="required_text"),
            )
            evaluator = HarnessArtifactEvaluator(
                self.root,
                model_review_config=self.model_review_config,
                assessment=self.assessment,
                assessment_profile=self.assessment_profile,
            )
            default_skill = "office.normal"
        elif provider == "workagent":
            adapter = WorkAgentOfficeAdapter(
                self.root,
                self.workagent_config,
                input_base=self.input_base,
                agent_instructions=self.agent_instructions,
            )
            evaluator = HarnessArtifactEvaluator(
                self.root,
                model_review_config=self.model_review_config,
                assessment=self.assessment,
                assessment_profile=self.assessment_profile,
            )
            if repair_request is not None:
                adapter.repair_request = repair_request
            default_skill = "office.workagent"
        elif provider == "com":
            adapter = ComOfficeAdapter(
                self.root / "generated",
                PilotSkillConfig(marker_source="required_text"),
                self.capability_report,
            )
            evaluator = HarnessArtifactEvaluator(
                self.root,
                model_review_config=self.model_review_config,
                assessment=self.assessment,
                assessment_profile=self.assessment_profile,
            )
            default_skill = "office.com"
        elif provider == "libreoffice":
            adapter = UnavailableOfficeAdapter("libreoffice", "LibreOffice provider is unavailable on this machine")
            evaluator = HarnessArtifactEvaluator(
                self.root,
                model_review_config=self.model_review_config,
                assessment=self.assessment,
                assessment_profile=self.assessment_profile,
            )
            default_skill = "office.libreoffice"
        else:
            raise ValueError(f"unknown execution provider: {provider}")
        if provider == "smoke" and use_office and self.execution_provider is None:
            raise ValueError("Office task cannot use smoke provider implicitly")
        if provider != "smoke" and not use_office:
            raise ValueError(f"Office provider {provider} requires an Office task domain")
        self._orchestrator = Orchestrator(
            artifact_store=self.store.files,
            trace_store=self.store.logs,
            adapter=adapter,
            evaluator=evaluator,
        )
        self._provider = provider
        result = self._orchestrator.run(task, skill_id or default_skill, max_attempts=max_attempts,
                                        defer_assessment=defer_assessment)
        if defer_assessment:
            result['_attempt_root'] = str(self.root.resolve())
            return result
        return self._finish(task, result)

    def _assess_execution(self, task, result):
        return self._finish(task, self._orchestrator.assess_result(task, result))

    def _finish(self, task, result):
        if self._provider == "workagent":
            if not self.workagent_config.verify_com:
                com = {"ok": False, "status": "disabled"}
            elif result["state"] != "SUCCEEDED":
                com = {"ok": False, "status": "not_run", "error": "Office evaluation did not pass"}
            else:
                com = verify_stored_office_artifacts(result["artifacts"], task.domain.lower(), self.root)
                if com["ok"] is not True:
                    result["state"] = "UNAVAILABLE" if com["status"] in {"unavailable", "timeout"} else "FAILED"
                    result["failure"] = {
                        "message": com["error"],
                        "status": com["status"],
                        "retryable": False,
                        "provider": "office-com",
                    }
                    result["evaluation"]["passed"] = False
                    if result['evaluation'].get('score_semantics')=='task-v2':
                        # Shared artifact facts remain in their immutable reports;
                        # an additional required reopening channel is unqualified.
                        evaluation=result['evaluation']
                        evaluation.update(score=None,quality_score=None,task_acceptance='INCOMPLETE')
                        evaluation['assessment_outcome'].update(status='incomplete',score=None,quality_score=None,
                            task_acceptance='INCOMPLETE',failure_origin='assessment_gap')
                        evaluation.setdefault('channel_status',{})['assessment']='incomplete'
                    result["evaluation"]["critical_failures"].append(
                        "required COM verification: " + com["error"]
                    )
                    self.store.logs.set_state(result["run_id"], result["state"])
            result["com_reopen"] = com
            if "evaluation" in result:
                result["evaluation"].setdefault("channel_status", {})["com"] = com["status"]
            persist_com_result(self.root, com)
            if com["status"] != "not_run":
                self.store.logs.append_event(result["run_id"], "com_reopen", com)
        result['_attempt_root'] = str(self.root.resolve())
        result['assessment_profile']=self.assessment_profile or 'default'
        return result

    def resume(self, run_id: str) -> dict:
        """Read the persisted state and trace for a run in this directory."""

        return {
            "run_id": run_id,
            "state": self.store.logs.get_state(run_id),
            "events": self.store.logs.events(run_id),
        }


def run_once(task: TaskSpec, root: str | Path) -> dict:
    """Convenience function for scripts that need one normal run."""

    return Run(root).execute(task)


__all__ = ["ComOfficeAdapter", "LocalOfficeAdapter", "MockWorkAgentAdapter", "Run", "UnavailableOfficeAdapter", "run_once"]
