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
