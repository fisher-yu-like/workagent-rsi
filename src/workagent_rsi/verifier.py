from __future__ import annotations

from copy import deepcopy
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .candidate_normalization import parse_candidate_json
from .hashing import canonical_json_hash
from .leakage import LeakageCritic
from .rsi_contracts import BehaviorProbeResult, CandidatePatch, VerificationReport
from .skill_runtime import PilotSkillConfig
from .view_safety import checked_path, ordinary_file
from .workagent_provider import WorkAgentSkill

Runner = Callable[[list[str], Path, int], subprocess.CompletedProcess[str]]


def _run(command, cwd, timeout):
    # Retained injection seam for callers; JSON skill verification never calls it.
    return subprocess.run(command, cwd=cwd, timeout=timeout, capture_output=True, text=True, check=False)


class VerificationPolicy(BaseModel):
    model_config = ConfigDict(extra='forbid')
    allowed_targets: set[str]
    protected_paths: set[str] = Field(default_factory=set)
    protected_values: list[str] = Field(default_factory=list)
    required_instruction_rules: list[str] = Field(default_factory=list)
    require_behavior: bool | None = None
    timeout_seconds: int = Field(default=120, ge=1)


class CandidateVerifier:
    def __init__(self, runner: Runner = _run, *, behavior_probe=None):
        self.runner, self.behavior_probe = runner, behavior_probe

    def identity_config(self):
        probe = self.behavior_probe
        return {'verifier': 'independent-skill-verifier-v2',
                'behavior_probe': probe.identity_config() if hasattr(probe, 'identity_config') else
                None if probe is None else 'unversioned-trusted-callback'}

    def verify(self, candidate, workspace, policy, *, skill_model=None, parent_package=None,
               parent_version=None, edit_budget=None, behavior_probe=None, candidate_version=None):
        checks, violations, warnings = ['path_policy'], [], []
        schema = safety = 'not_run'
        behavior, required = 'not_run', False
        details = {'candidate_authored_tests': 'not_run', 'compile': 'not_applicable'}
        artifacts = {}
        parent, proposed = None, None
        try:
            candidate = CandidatePatch.model_validate(candidate.model_dump())
            policy = VerificationPolicy.model_validate(policy.model_dump())
            root = checked_path(workspace)
            if not root.is_dir():
                raise ValueError('candidate workspace must be a directory')
            for edit in candidate.atomic_edits:
                if (edit.target_path != 'skill.json' or edit.target_path not in policy.allowed_targets
                        or edit.target_path in policy.protected_paths):
                    violations.append('target not allowlisted or protected: ' + edit.target_path)
            if violations:
                safety = 'failed'
            else:
                checks.append('patch_schema')
                payloads = []
                for edit in candidate.atomic_edits:
                    try:
                        payload = parse_candidate_json(edit.patch)
                    except ValueError as exc:
                        raise ValueError('invalid patch JSON: ' + str(exc)) from exc
                    if not isinstance(payload, dict) or len(payload) != 1:
                        raise ValueError('patch JSON must update exactly one skill field')
                    payloads.append(payload)
                parent = deepcopy(parent_package) if parent_package is not None else parse_candidate_json(
                    ordinary_file(root/'skill.json').read_text(encoding='utf-8'))
                if not isinstance(parent, dict):
                    raise ValueError('parent package must be a JSON object')
                model = skill_model or (WorkAgentSkill if 'instructions' in parent else PilotSkillConfig)
                if model not in {WorkAgentSkill, PilotSkillConfig}:
                    raise ValueError('unsupported skill model; no editable-field policy is registered')
                model.model_validate_json(json.dumps(parent), strict=True)
                trusted_parent = parent_version if parent_version is not None else parent.get('version', candidate.parent_version)
                trusted_budget = edit_budget if edit_budget is not None else candidate.edit_budget
                if type(trusted_budget) is not int or trusted_budget < 1:
                    raise ValueError('trusted edit budget must be a positive integer')
                if candidate.parent_version != trusted_parent:
                    raise ValueError('candidate parent version mismatch')
                if parent.get('version', trusted_parent) != trusted_parent:
                    raise ValueError('parent package version mismatch')
                if candidate.edit_budget != trusted_budget or len(payloads) > trusted_budget:
                    raise ValueError('candidate exceeds or misstates trusted edit budget')
                editable = {'instructions'} if model is WorkAgentSkill else {
                    'marker_source', 'sales_rows', 'sales_chart', 'sales_number_format'}
                seen = set()
                for payload in payloads:
                    field = next(iter(payload))
                    if field not in editable or field not in parent:
                        raise ValueError('unknown, immutable or absent skill field: ' + field)
                    if field in seen:
                        raise ValueError('duplicate or overlapping skill field: ' + field)
                    seen.add(field)
                    if type(payload[field]) is not type(parent[field]):
                        raise ValueError('skill field type mismatch: ' + field)
                # Complete patch admission precedes application to a private copy.
                proposed = deepcopy(parent)
                for payload in payloads:
                    proposed.update(payload)
                if candidate_version is not None and 'version' in proposed:
                    proposed['version'] = candidate_version
                model.model_validate_json(json.dumps(proposed), strict=True)
                schema = 'passed'
                checks.extend(['parent_version', 'edit_budget', 'skill_model', 'artifact_execution_config', 'leakage'])
                artifacts = {'parent_package_hash': canonical_json_hash(parent),
                             'candidate_package_hash': canonical_json_hash(proposed),
                             'skill_model': model.__name__,
                             'parent_identity_source': 'trusted_caller' if parent_package is not None else 'export_compatibility'}
                violations.extend(LeakageCritic(policy.protected_values, list(policy.protected_paths)).scan(candidate))
                instructions = proposed.get('instructions', '')
                lines = {line.strip() for line in instructions.splitlines()}
                if any(rule.strip() not in lines for rule in policy.required_instruction_rules):
                    violations.append('candidate removed or weakened a required standalone instruction rule')
                safety = 'failed' if violations else 'passed'
                required = policy.require_behavior if policy.require_behavior is not None else model is WorkAgentSkill
                if parent_version is None or edit_budget is None:
                    warnings.append('compatibility caller did not bind registry parent and budget explicitly')
                checks.append('compile_not_applicable')
                if (root/'tests').exists() or candidate.new_tests:
                    warnings.append('candidate-authored tests are supplementary and never executed on the host')
                probe = behavior_probe if behavior_probe is not None else self.behavior_probe
                if not violations and probe is not None:
                    checks.append('independent_behavior_probe')
                    try:
                        result = BehaviorProbeResult.model_validate(probe(parent_package=deepcopy(parent),
                            candidate_package=deepcopy(proposed), timeout_seconds=policy.timeout_seconds))
                        details['behavior_probe'] = result.model_dump(mode='json')
                        behavior = result.status
                        if result.protected_regressions or result.failed_checks:
                            behavior = 'failed'
                        if behavior == 'passed' and not (
                            result.evidence_kind == 'isolated_run' and result.backend in {'docker', 'apptainer-ssh'}
                            and result.isolation_verified and result.independent_tasks_verified and result.cleanup_confirmed
                            and result.taskset_hash and result.evidence_refs
                            and result.parent_package_hash == artifacts['parent_package_hash']
                            and result.candidate_package_hash == artifacts['candidate_package_hash']):
                            behavior = 'not_run'
                            warnings.append('probe lacks qualified independent isolation/identity/cleanup evidence')
                        if behavior == 'failed':
                            violations.append('independent behavior probe failed or protected behavior regressed')
                    except Exception as exc:
                        behavior = 'error'
                        details['behavior_error'] = type(exc).__name__ + ': ' + str(exc)
        except (OSError, ValueError, TypeError) as exc:
            schema = 'failed'
            violations.append('skill schema or boundary rejected: ' + str(exc))
        if behavior == 'not_run':
            warnings.append('isolated behavior not run; skill quality remains unverified')
        passed = (schema == safety == 'passed' and not violations
                  and behavior not in {'failed', 'error', 'unavailable'} and (not required or behavior == 'passed'))
        payload = dict(candidate_id=candidate.candidate_id, passed=passed, critical_violations=violations,
            warnings=warnings, executed_checks=checks, test_results=details, artifact_results=artifacts,
            schema_status=schema, safety_status=safety, behavior_status=behavior,
            compile_status='not_applicable', behavior_required=required,
            quality_verified=passed and behavior == 'passed')
        return VerificationReport(**payload, evidence_refs=[canonical_json_hash(payload)])
