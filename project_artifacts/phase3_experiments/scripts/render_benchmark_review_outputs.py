"""Render saved successful exports once, with at most twenty remote renders.

Generation has a separate maximum of twenty executions. These disjoint caps
keep their combined logical task operations within the approved forty. A failed
render retains its reservation and is never retried automatically.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from workagent_rsi.apptainer_sandbox import ApptainerPolicy, ApptainerSSHExecutor
from workagent_rsi.artifact_renderer import OfficeArtifactRenderer
from workagent_rsi.hashing import sha256_file
from workagent_rsi.view_safety import ordinary_file, relative_reference
from run_benchmark_review_jobs import validate_run_plan


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def render_available(plan_path: Path, actual_run: Path, policy_path: Path, output: Path, *, watch=False):
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    count = validate_run_plan(plan)
    if output.exists():
        raise FileExistsError('new render cache required; never replay an interrupted reservation')
    frozen = json.loads((actual_run / 'run-inputs.json').read_text(encoding='utf-8'))
    if frozen['plan_sha256'] != sha256_file(plan_path):
        raise ValueError('render plan differs from generation plan')
    policy = ApptainerPolicy.model_validate_json(policy_path.read_text(encoding='utf-8'))
    renderer = OfficeArtifactRenderer(output / 'worker-evidence', sandbox=ApptainerSSHExecutor(policy),
                                      dpi=96, max_pages=40, timeout_seconds=90)
    output.mkdir(parents=True)
    results, seen, records, finished = [], set(), [], False
    started = time.monotonic()
    jobs = {j['case_id']: j for j in plan['jobs']}
    while True:
        if time.monotonic() - started > 7200:
            break
        try:
            records = json.loads((actual_run / 'job-results.json').read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            # Controller evidence is written between jobs; this is a read retry,
            # not a model or rendering retry.
            time.sleep(1)
            continue
        for row in records:
            identity = row['case_id']
            if identity in seen or row['status'] == 'reserved':
                continue
            execution = row.get('execution', {})
            if execution.get('status') != 'succeeded':
                seen.add(identity)
                continue
            job = jobs[identity]
            reference = 'outputs/' + job['expected_output']
            if reference not in execution.get('artifact_refs', []):
                seen.add(identity)
                continue
            artifact = ordinary_file(actual_run / 'cases' / identity / relative_reference(reference))
            if len(results) >= count:
                raise ValueError('approved twenty-render cap exhausted')
            entry = {'case_id': identity, 'artifact_sha256': sha256_file(artifact), 'status': 'reserved',
                     'reserved_at': datetime.now(timezone.utc).isoformat()}
            results.append(entry)
            seen.add(identity)
            write(output / 'render-results.json', results)
            try:
                result = renderer.render(artifact, job['domain'], entry['artifact_sha256'])
                entry.update(status=result.status, render=result.model_dump(mode='json'))
            except Exception as exc:
                entry.update(status='error', error=type(exc).__name__ + ': ' + str(exc))
            write(output / 'render-results.json', results)
            print(json.dumps({'case_id': identity, 'status': entry['status'],
                              'pages': len(entry.get('render', {}).get('pages', [])), 'render_reservations': len(results)}), flush=True)
        finished = len(records) == count and all(r['status'] != 'reserved' for r in records)
        if not watch or finished or time.monotonic() - started > 7200:
            break
        time.sleep(2)
    executions = json.loads((actual_run / 'server-operations.json').read_text(encoding='utf-8')).get('reserved', 0)
    if executions > count or executions + len(results) > count * 2:
        raise ValueError('combined generation/render budget exceeded')
    report = {'execution_reservations': executions, 'render_reservations': len(results),
        'combined_server_operations': executions + len(results), 'approved_limit': count * 2,
        'available_renders': sum(r['status'] == 'available' for r in results),
        'actual_rendered_pages': sum(len(r.get('render', {}).get('pages', [])) for r in results),
        'generation_finished': finished, 'model_calls': 0, 'judge_calls': 0,
        'plan_sha256': sha256_file(plan_path), 'source_sha256': sha256_file(Path(__file__))}
    write(output / 'render-summary.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--actual-run', type=Path, required=True)
    parser.add_argument('--sandbox-policy', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    print(json.dumps(render_available(args.plan, args.actual_run, args.sandbox_policy, args.output, watch=args.watch)))
