"""Task-only transport and fail-closed behavior, without SSH or model calls."""
import base64
import hashlib
import json
import subprocess

import pytest
from pydantic import ValidationError

from workagent_rsi.apptainer_sandbox import ApptainerPolicy, ApptainerSSHExecutor
from workagent_rsi.workagent_provider import WorkAgentConfig, CodexOfficeProvider, _execute_native_tool


def policy(**changes):
    values = dict(ssh_host="offline-test-host", uid=1001, gid=1001,
                  remote_image="/tmp/authored-runtime", remote_image_sha256="a"*64)
    values.update(changes)
    return ApptainerPolicy(**values)


def workspace(tmp_path):
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs/source.txt").write_text("source")
    (tmp_path / "script.py").write_text("raise AssertionError('never run outside sandbox')")
    (tmp_path / "protected.json").write_text("excluded sentinel")
    return tmp_path


def output_file(name="outputs/result.txt", content=b"authored output"):
    return {name: {"data": base64.b64encode(content).decode(), "sha256": hashlib.sha256(content).hexdigest()}}


def test_only_selected_files_cross_ssh_and_result_is_exposed_through_native_tool(tmp_path):
    root = workspace(tmp_path)
    requests = []
    def transport(p, request):
        requests.append(request)
        assert set(request["files"]) == {"inputs/source.txt", "script.py"}
        return {"status": "succeeded", "failure_origin": None, "returncode": 0,
                "files": output_file(), "cleanup": {"confirmed_absent": True}}
    executor = ApptainerSSHExecutor(policy(), transport=transport)
    result = _execute_native_tool("run_python", {"path": "script.py"}, root, sandbox=executor)
    assert result["ok"] is True and result["returncode"] == 0
    assert (root / "outputs/result.txt").read_text() == "authored output"
    assert "excluded sentinel" not in json.dumps(requests)
    assert result["execution"]["artifact_refs"] == ["outputs/result.txt"]


@pytest.mark.parametrize("name", ["../escape.txt", "outputs/../../escape", "outputs\\escape", "scratch/x:y", "/outputs/x"])
def test_entire_remote_response_is_checked_before_export(tmp_path, name):
    root = workspace(tmp_path)
    def transport(p,request):
        return {"status": "succeeded", "failure_origin": None,
                "files": {**output_file(), **output_file(name)}, "cleanup": {"confirmed_absent": True}}
    outcome = ApptainerSSHExecutor(policy(), transport=transport).run(root / "script.py", root, 1)
    assert outcome.status == "failed"
    assert not (root / "outputs/result.txt").exists()


def test_unconfirmed_remote_cleanup_quarantines_executor(tmp_path):
    root = workspace(tmp_path)
    calls = []
    def transport(p,request):
        calls.append(request)
        return {"status": "succeeded", "files": output_file(), "cleanup": {"confirmed_absent": False}}
    executor = ApptainerSSHExecutor(policy(), transport=transport)
    assert executor.run(root / "script.py", root, 1).status == "unavailable"
    assert executor.probe()["status"] == "unavailable"
    assert executor.run(root / "script.py", root, 1).status == "unavailable"
    assert len(calls) == 1 and not (root / "outputs/result.txt").exists()


def test_remote_timeout_stays_explicit_with_confirmed_service_cleanup(tmp_path):
    root = workspace(tmp_path)
    executor = ApptainerSSHExecutor(policy(), transport=lambda p,r: {
        "status": "timeout", "failure_origin": "agent_execution", "cleanup": {"confirmed_absent": True}})
    result = executor.run(root / "script.py", root, 1)
    assert result.status == "timeout" and result.failure_origin == "agent_execution"
    assert result.artifact_refs == []


def test_transport_failure_never_falls_back_to_host_python(tmp_path):
    root = workspace(tmp_path)
    def transport(p,r):
        raise subprocess.TimeoutExpired("authored ssh timeout", 1)
    executor = ApptainerSSHExecutor(policy(), transport=transport)
    result = executor.run(root / "script.py", root, 1)
    assert result.status == "unavailable" and result.failure_origin == "environment"
    assert executor.probe()["status"] == "unavailable"


@pytest.mark.parametrize("changes", [{"ssh_host": "-oProxyCommand=bad"}, {"uid": 0}, {"remote_image": "relative"},
                                     {"remote_image_sha256": "unknown"}, {"remote_image": "/tmp/x:rw"}, {"cpus": 3.0},
                                     {"max_total_bytes": 67108864}])
def test_remote_configuration_cannot_inject_arguments_or_remove_limits(changes):
    with pytest.raises(ValidationError):
        policy(**changes)


def test_explicit_config_selects_apptainer_without_connecting():
    config = WorkAgentConfig(backend="openai-chat", sandbox_policy=policy().model_dump())
    assert isinstance(config.sandbox_policy, ApptainerPolicy)
    provider = CodexOfficeProvider(config)
    assert isinstance(provider.sandbox, ApptainerSSHExecutor)
