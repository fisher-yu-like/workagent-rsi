"""Explicit fixed-task probe adapter; never execute candidate-authored tests."""
import json
from pathlib import Path
import shutil
from uuid import uuid4

from .hashing import canonical_json_hash, sha256_file
from .rsi_contracts import BehaviorProbeResult
from .view_safety import checked_path, ordinary_file, relative_reference


class FixedSandboxBehaviorProbe:
    """Prepare only fixed program/tasks and two JSON packages for T04 execution.

    The program and taskset are trusted verifier configuration, frozen by hash.
    Qualification is explicitly unverified/unit_fixture until a real external
    run is performed; fixtures cannot establish quality. No default executor.
    """
    def __init__(self, *, executor, program, program_sha256, taskset, taskset_sha256,
                 output_root, qualification='unverified'):
        if qualification not in {'unverified', 'unit_fixture', 'isolated_run'}:
            raise ValueError('unknown behavior qualification source')
        self.executor, self.program, self.taskset = executor, Path(program), Path(taskset)
        self.program_hash, self.taskset_hash = program_sha256, taskset_sha256
        self.output_root, self.qualification = Path(output_root), qualification

    def identity_config(self):
        return {'probe': 'fixed-sandbox-behavior-v1', 'program_sha256': self.program_hash,
                'taskset_sha256': self.taskset_hash, 'qualification': self.qualification,
                'sandbox_policy': self.executor.policy.model_dump(mode='json') if self.executor is not None else None}

    def __call__(self, *, parent_package, candidate_package, timeout_seconds):
        base = dict(status='not_run', evidence_kind=self.qualification,
                    parent_package_hash=canonical_json_hash(parent_package),
                    candidate_package_hash=canonical_json_hash(candidate_package))
        if self.executor is None:
            return BehaviorProbeResult(**base).model_dump()
        for path, expected in [(self.program, self.program_hash), (self.taskset, self.taskset_hash)]:
            if sha256_file(ordinary_file(path)) != expected:
                raise ValueError('fixed independent behavior source hash mismatch')
        manifest = json.loads(self.taskset.read_text(encoding='utf-8'))
        tasks = manifest.get('tasks', [])
        if (not tasks or any(not isinstance(t, dict) or not isinstance(t.get('task_id'), str)
                             or not t['task_id'] or type(t.get('protected')) is not bool for t in tasks)
                or len({t['task_id'] for t in tasks}) != len(tasks)):
            raise ValueError('fixed behavior taskset must declare unique tasks and protection flags')
        policy = self.executor.policy
        if policy.backend != 'apptainer-ssh' or policy.network != 'none':
            raise ValueError('current fixed probe requires the qualified Apptainer boundary')
        root = checked_path(self.output_root)/uuid4().hex
        (root/'inputs').mkdir(parents=True, exist_ok=False)
        for name, value in [('parent.json', parent_package), ('candidate.json', candidate_package)]:
            (root/'inputs'/name).write_text(json.dumps(value), encoding='utf-8')
        shutil.copyfile(self.taskset, root/'inputs/tasks.json')
        script = root/'fixed_probe.py'
        shutil.copyfile(self.program, script)
        if sha256_file(script) != self.program_hash or sha256_file(root/'inputs/tasks.json') != self.taskset_hash:
            raise ValueError('fixed behavior source changed during copy')
        outcome = self.executor.run(script, root, timeout_seconds)
        base.update(backend='apptainer-ssh', taskset_hash=self.taskset_hash)
        if outcome.status != 'succeeded':
            base['status'] = 'unavailable'
            return BehaviorProbeResult(**base, evidence_refs=outcome.trace_refs).model_dump()
        traces = []
        for ref in outcome.trace_refs:
            safe = relative_reference(ref)
            traces.append(json.loads(ordinary_file(root/Path(*safe.parts)).read_text(encoding='utf-8')))
        if not traces:
            raise ValueError('behavior execution has no trusted sandbox trace')
        trace = traces[-1]
        isolated = (trace.get('resource_observations', {}).get('passed') is True
                    and trace.get('capability', {}).get('image_sha256') == policy.remote_image_sha256
                    and trace.get('cleanup', {}).get('confirmed_absent') is True)
        if not isolated:
            raise ValueError('behavior isolation/runtime/cleanup evidence is incomplete')
        report_path = ordinary_file(root/'outputs/behavior.json')
        report = json.loads(report_path.read_text(encoding='utf-8'))
        if (report.get('parent_package_hash') != base['parent_package_hash']
                or report.get('candidate_package_hash') != base['candidate_package_hash']
                or report.get('taskset_hash') != self.taskset_hash):
            raise ValueError('behavior output is not bound to this package/taskset')
        rows = report.get('rows', [])
        if (not isinstance(rows, list) or len(rows) != len(tasks)
                or any(not isinstance(r, dict) or type(r.get('parent_passed')) is not bool
                       or type(r.get('candidate_passed')) is not bool for r in rows)
                or {r.get('task_id') for r in rows} != {t['task_id'] for t in tasks}):
            raise ValueError('behavior output does not cover the fixed taskset exactly once')
        protected = {t['task_id'] for t in tasks if t['protected']}
        regressions = sum(r['task_id'] in protected and r['parent_passed'] and not r['candidate_passed'] for r in rows)
        failed = [r['task_id'] for r in rows if not r['candidate_passed']]
        for path, expected in [(self.program, self.program_hash), (self.taskset, self.taskset_hash)]:
            if sha256_file(ordinary_file(path)) != expected:
                raise ValueError('fixed behavior source changed during execution')
        base.update(status='failed' if failed or regressions else 'passed')
        return BehaviorProbeResult(**base, isolation_verified=True, independent_tasks_verified=True,
            cleanup_confirmed=True, protected_regressions=regressions, failed_checks=failed,
            evidence_refs=[sha256_file(report_path), *outcome.trace_refs]).model_dump()
