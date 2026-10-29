"""Offline safety controls for the explicit authored-qualification CLI runner."""
from datetime import datetime,timezone
import importlib
import json
from pathlib import Path
import subprocess

import pytest


@pytest.fixture
def cli_module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'project_artifacts/phase3_experiments/scripts'))
    return importlib.import_module('qualification_cli')


def policy(tmp_path,**updates):
    value={'allow_live_calls':True,'approved_by_user':True,'provider':'codex-cli','model':'gpt-6.1-sol',
        'max_model_calls':2,'max_tool_calls':32,'max_wall_seconds':10,
        'approved_at':datetime.now(timezone.utc).isoformat(),'approval_source':'AUTHORED UNIT POLICY; no external calls'}
    value.update(updates)
    path=tmp_path/'approved-policy.json';path.write_text(json.dumps(value))
    return path


def test_disabled_policy_never_starts_child(cli_module,tmp_path):
    with pytest.raises(ValueError,match='disabled'):
        cli_module.QualificationCLI(policy(tmp_path,allow_live_calls=False),runner=lambda *a:pytest.fail('child'))


def test_interrupted_request_keeps_full_time_reservation(cli_module,tmp_path):
    seen=[]
    def interrupted(*args):seen.append(args);raise subprocess.TimeoutExpired('authored',10)
    runner=cli_module.QualificationCLI(policy(tmp_path),runner=interrupted)
    command=['authored-no-process','--model','gpt-6.1-sol','-']
    with pytest.raises(subprocess.TimeoutExpired):runner(command,tmp_path,10,'authored')
    with pytest.raises(ValueError,match='wall budget exhausted'):runner(command,tmp_path,10,'authored')
    assert len(seen)==1
    state=json.loads((tmp_path/'budget-state.json').read_text())
    assert state['reserved_wall_seconds']==10 and state['calls'][0]['status']=='failed'


def test_request_limit_and_changed_policy_fail_before_child(cli_module,tmp_path):
    seen=[]
    def completed(*args):seen.append(args);return subprocess.CompletedProcess(args[0],0,stdout='',stderr='')
    path=policy(tmp_path,max_model_calls=1)
    runner=cli_module.QualificationCLI(path,runner=completed)
    command=['authored-no-process','--model','gpt-6.1-sol','-']
    runner(command,tmp_path,2,'authored')
    with pytest.raises(ValueError,match='request budget exhausted'):runner(command,tmp_path,2,'authored')
    changed=json.loads(path.read_text());changed['max_model_calls']=100;path.write_text(json.dumps(changed))
    with pytest.raises(ValueError,match='policy changed'):runner(command,tmp_path,2,'authored')
    assert len(seen)==1


def test_unexpected_tool_activity_quarantines_subsequent_calls(cli_module,tmp_path):
    seen=[]
    def unexpected(*args):
        seen.append(args)
        return subprocess.CompletedProcess(args[0],0,stdout=json.dumps({'type':'item.completed','item':{'type':'mcp_tool_call'}}),stderr='')
    runner=cli_module.QualificationCLI(policy(tmp_path),runner=unexpected)
    command=['authored-no-process','--model','gpt-6.1-sol','-']
    with pytest.raises(ValueError,match='unexpected tool'):runner(command,tmp_path,2,'authored')
    with pytest.raises(ValueError,match='quarantined'):runner(command,tmp_path,2,'authored')
    assert len(seen)==1


def test_existing_owner_lock_is_preserved(cli_module,tmp_path):
    runner=cli_module.QualificationCLI(policy(tmp_path),runner=lambda *a:pytest.fail('child'))
    lock=tmp_path/'budget.lock';lock.write_text('other owner')
    with pytest.raises(FileExistsError):runner(['authored','--model','gpt-6.1-sol','-'],tmp_path,2,'authored')
    assert lock.read_text()=='other owner'


def test_wait_beyond_timeout_is_fully_charged_and_blocks_next_request(cli_module,tmp_path,monkeypatch):
    clock=iter([0,35,36]);monkeypatch.setattr(cli_module.time,'monotonic',lambda:next(clock))
    seen=[]
    def delayed(*args):seen.append(args);raise subprocess.TimeoutExpired('authored',10)
    runner=cli_module.QualificationCLI(policy(tmp_path),runner=delayed)
    command=['authored','--model','gpt-6.1-sol','-']
    with pytest.raises(subprocess.TimeoutExpired):runner(command,tmp_path,10,'authored')
    state=json.loads((tmp_path/'budget-state.json').read_text())
    assert state['reserved_wall_seconds']==35 and state['calls'][0]['charged_wall_seconds']==35
    assert state['calls'][0]['elapsed_limit_exceeded']
    with pytest.raises(ValueError,match='wall budget exhausted'):runner(command,tmp_path,10,'authored')
    assert len(seen)==1


def test_late_success_is_rejected_instead_of_admitted(cli_module,tmp_path,monkeypatch):
    clock=iter([0,35,35]);monkeypatch.setattr(cli_module.time,'monotonic',lambda:next(clock))
    def late(*args):return subprocess.CompletedProcess(args[0],0,stdout='',stderr='')
    runner=cli_module.QualificationCLI(policy(tmp_path,max_wall_seconds=100),runner=late)
    with pytest.raises(TimeoutError,match='actual request elapsed'):runner(['authored','--model','gpt-6.1-sol','-'],tmp_path,10,'authored')
    state=json.loads((tmp_path/'budget-state.json').read_text())
    assert state['reserved_wall_seconds']==35 and state['calls'][0]['status']=='failed'
