"""No approval means no calls; generated source stays data on Windows."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


def script():
    path = Path(__file__).parents[1] / 'project_artifacts/phase3_experiments/scripts/run_benchmark_review_jobs.py'
    spec = importlib.util.spec_from_file_location('benchmark_review_jobs', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_disabled_live_policy_does_not_create_run_or_call_model(tmp_path):
    module = script()
    plan = tmp_path / 'plan.json'
    plan.write_text(json.dumps({'job_count': 20, 'jobs': [{}] * 20}), encoding='utf-8')
    policy = tmp_path / 'policy.json'
    policy.write_text('{"allow_live_calls": false}', encoding='utf-8')
    with pytest.raises(ValueError, match='disabled'):
        module.run(plan, policy, tmp_path / 'not-read.json', tmp_path / 'run')
    assert not (tmp_path / 'run').exists()


def test_generated_program_is_not_executed_locally_and_cli_tools_are_disabled(tmp_path, monkeypatch):
    module = script()
    sentinel = tmp_path / 'must-not-exist'
    program = f'from pathlib import Path\nPath({str(sentinel)!r}).write_text("executed")'
    monkeypatch.setattr(module.shutil, 'which', lambda name: 'codex-test')
    def runner(command, cwd, timeout, prompt):
        assert '--ignore-user-config' in command and '--ephemeral' in command
        assert 'features.shell_tool=false' in command
        assert 'features.multi_agent=false' in command
        assert Path(cwd).parent != Path(__file__).parents[1]
        out = Path(command[command.index('--output-last-message') + 1])
        out.write_text(json.dumps({'python_source': program, 'summary': 'fixture'}), encoding='utf-8')
        return subprocess.CompletedProcess(command, 0, '', '')
    returned = module.generate({'instruction': 'authored fixture'}, tmp_path, runner)
    assert returned == program
    assert not sentinel.exists()


def test_recovery_registers_existing_relative_run_without_rerunning_models(tmp_path, monkeypatch):
    from openpyxl import Workbook
    from workagent_rsi.hashing import sha256_file
    module = script()
    monkeypatch.chdir(tmp_path)
    root = Path('relative-run')
    case = root / 'cases' / 'one'
    (case / 'inputs').mkdir(parents=True)
    (case / 'outputs').mkdir()
    (case / 'inputs/source.xlsx').write_bytes(b'authored input identity')
    book = Workbook()
    book.active['A1'] = 'authored output fixture'
    book.save(case / 'outputs/output.xlsx')
    source = '# authored test fixture; never executed\n'
    (case / 'generate.py').write_text(source, encoding='utf-8')
    provider = root / 'provider-records/one'
    provider.mkdir(parents=True)
    (provider / 'response.json').write_text(json.dumps({'python_source': source, 'summary': 'fixture'}), encoding='utf-8')
    trace = case / 'provider_records/sandbox/trace.json'
    trace.parent.mkdir(parents=True)
    trace.write_text(json.dumps({'outcome': {'status': 'succeeded'}, 'cleanup': {'confirmed_absent': True}}), encoding='utf-8')
    job = {'case_id': 'one', 'expected_output': 'output.xlsx', 'domain': 'excel', 'instruction': 'Authored test fixture.',
           'source_family': 'fixture-family', 'source_refs': ['authored-unit-fixture'],
           'inputs': {'source.xlsx': sha256_file(case / 'inputs/source.xlsx')}}
    jobs = [job] + [{**job, 'case_id': f'failed-{i}'} for i in range(19)]
    plan = Path('plan.json')
    plan.write_text(json.dumps({'job_count': 20, 'jobs': jobs}), encoding='utf-8')
    (root / 'run-inputs.json').write_text(json.dumps({'plan_sha256': sha256_file(plan)}), encoding='utf-8')
    records = [{'case_id': 'one', 'status': 'failed', 'error': 'authored controller path error', 'execution': {
        'status': 'succeeded', 'artifact_refs': ['outputs/output.xlsx'], 'trace_refs': ['provider_records/sandbox/trace.json']}}]
    records += [{'case_id': j['case_id'], 'status': 'failed'} for j in jobs[1:]]
    (root / 'job-results.json').write_text(json.dumps(records), encoding='utf-8')
    original = (root / 'job-results.json').read_bytes()
    result = module.recover_saved_outputs(plan, root)
    assert result['actual_natural_artifacts'] == 1
    assert result['new_model_calls'] == result['new_server_operations'] == 0
    assert (root / 'job-results.json').read_bytes() == original
    recovered = json.loads((root / 'natural-manifest.recovered.json').read_text(encoding='utf-8'))
    assert recovered['cases'][0]['artifact_path'] == 'cases/one/outputs/output.xlsx'
    (case / 'generate.py').write_text('# changed source', encoding='utf-8')
    result = module.recover_saved_outputs(plan, root)
    assert result['actual_natural_artifacts'] == 0
    assert 'differs' in result['rejected'][0]['reason']


def test_repair_proposal_cannot_change_inputs_or_repeat_successful_jobs(tmp_path):
    from copy import deepcopy
    from workagent_rsi.hashing import sha256_file
    module = script()
    job = {'case_id': 'failed-case', 'base_task_id': 'original', 'variant_id': 'original/one',
           'domain': 'excel', 'source_family': 'family', 'inputs': {'source.xlsx': 'a'*64}, 'expected_output': 'output.xlsx'}
    parent = tmp_path / 'parent.json'
    parent.write_text(json.dumps({'jobs': [job]}), encoding='utf-8')
    records = tmp_path / 'records.json'
    records.write_text(json.dumps([{'case_id': 'failed-case', 'execution': {'status': 'failed'}}]), encoding='utf-8')
    plan = {'schema_version': 'benchmark-natural-output-repair-plan-v1', 'job_count': 1, 'jobs': [deepcopy(job)],
            'parent_plan': str(parent), 'parent_plan_sha256': sha256_file(parent),
            'parent_job_records': str(records), 'parent_job_records_sha256': sha256_file(records)}
    assert module.validate_run_plan(plan) == 1
    changed = deepcopy(plan)
    changed['jobs'][0]['inputs'] = {'other.xlsx': 'b'*64}
    with pytest.raises(ValueError, match='preserve'):
        module.validate_run_plan(changed)
    records.write_text(json.dumps([{'case_id': 'failed-case', 'execution': {'status': 'succeeded'}}]), encoding='utf-8')
    plan['parent_job_records_sha256'] = sha256_file(records)
    with pytest.raises(ValueError, match='actual failed'):
        module.validate_run_plan(plan)
