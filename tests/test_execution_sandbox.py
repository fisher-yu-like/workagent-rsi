"""Independent T04 unit fixtures; fake Docker never qualifies OS isolation."""
import json
import os
from pathlib import Path
import subprocess
import io
import sys

import pytest
from pydantic import ValidationError

from workagent_rsi.execution_sandbox import SandboxExecutor, SandboxPolicy, _docker_run
from workagent_rsi.workagent_provider import _execute_native_tool, CodexOfficeProvider, WorkAgentConfig


IMAGE = "workagent-runtime@sha256:" + "a" * 64
IMAGE_ID = "sha256:" + "b" * 64


class DockerStub:
    """A transport fixture only. Never executes the supplied script."""
    def __init__(self, *, exit_code=0, timeout=False, cleanup_fails=False, bad_output=False, changed_input=False):
        self.calls = []
        self.exit_code, self.timeout, self.cleanup_fails = exit_code, timeout, cleanup_fails
        self.bad_output, self.changed_input = bad_output, changed_input
        self.removed = False
        self.create = None

    def __call__(self, command, timeout, env):
        self.calls.append((command, timeout, env))
        args = command[3:]  # docker --host local_endpoint
        result = ""
        code = 0
        if args[0] == "info":
            result = json.dumps({"OSType": "linux", "ServerVersion": "stub"})
        elif args[:2] == ["image", "inspect"]:
            result = json.dumps([{"Id": IMAGE_ID, "RepoDigests": [IMAGE], "Os": "linux"}])
        elif args[0] == "create":
            self.create = args
            result = "stub-container-id"
        elif args[0] == "start":
            if self.timeout:
                raise subprocess.TimeoutExpired(command, timeout)
            mounts = [self.create[i+1] for i, x in enumerate(self.create) if x == "--mount"]
            def mounted(target):
                item = next(m for m in mounts if f"target={target}" in m)
                return Path(next(s[7:] for s in item.split(",") if s.startswith("source=")))
            (mounted("/task/outputs") / "result.txt").write_text("authored-stub-output", encoding="utf-8")
            if self.bad_output:
                os.link(mounted("/task/outputs") / "result.txt", mounted("/task/outputs") / "duplicate.txt")
            if self.changed_input:
                (mounted("/task") / "inputs" / "source.txt").chmod(0o644)
                (mounted("/task") / "inputs" / "source.txt").write_text("changed", encoding="utf-8")
            result = "stub stdout"
        elif args[0] == "inspect":
            if self.removed:
                result, code = "", 1
                return subprocess.CompletedProcess(command, code, result, "Error: No such object: " + args[-1])
            result = json.dumps({"ExitCode": self.exit_code, "OOMKilled": False, "Running": False})
        elif args[0] == "rm":
            if self.cleanup_fails:
                return subprocess.CompletedProcess(command, 1, "", "authored cleanup failure")
            self.removed = True
        return subprocess.CompletedProcess(command, code, result, "")


def task_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "inputs").mkdir(parents=True)
    (workspace / "inputs" / "source.txt").write_text("source sentinel", encoding="utf-8")
    (workspace / "script.py").write_text("raise AssertionError('unit tests must not execute me')", encoding="utf-8")
    (workspace / "hidden-evaluator.json").write_text("excluded sentinel", encoding="utf-8")
    return workspace


def test_actual_create_command_has_boundary_and_only_minimal_staged_mounts(tmp_path, monkeypatch):
    workspace = task_workspace(tmp_path)
    monkeypatch.setenv("WRSI_REVIEW_DUMMY_SECRET", "dummy-sentinel")
    docker = DockerStub()
    executor = SandboxExecutor(SandboxPolicy(image=IMAGE), runner=docker)
    outcome = executor.run(workspace / "script.py", workspace, 10)
    assert outcome.status == "succeeded"
    command = docker.create
    for flag in ("--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                 "--pids-limit=128", "--memory=2147483648", "--memory-swap=2147483648", "--cpus=2.0", "--pull=never"):
        assert flag in command
    assert command[command.index("--user")+1] == "65532:65532"
    mounts = [command[i+1] for i, x in enumerate(command) if x == "--mount"]
    assert len(mounts) == 3
    assert sum("readonly" in m for m in mounts) == 1
    assert not any(str(workspace) in m or "docker.sock" in m for m in mounts)
    assert "-i" in command and "HOME=/tmp" in command
    assert all("WRSI_REVIEW_DUMMY_SECRET" not in env for _, _, env in docker.calls)
    assert (workspace / "outputs" / "result.txt").read_text() == "authored-stub-output"
    assert (workspace / "inputs" / "source.txt").read_text() == "source sentinel"
    trace = json.loads((workspace / outcome.trace_refs[0]).read_text(encoding="utf-8"))
    assert trace["image_id"] == IMAGE_ID and trace["cleanup"]["confirmed_absent"] is True
    assert trace["staged_files"] == ["inputs/source.txt", "script.py"]


def test_unconfigured_backend_never_runs_a_host_script(tmp_path):
    workspace = task_workspace(tmp_path)
    def forbidden(*args, **kwargs):
        pytest.fail("no process may start without an immutable image")
    outcome = SandboxExecutor(SandboxPolicy(), runner=forbidden).run(workspace / "script.py", workspace, 1)
    assert outcome.status == "unavailable" and outcome.failure_origin == "environment"
    result = _execute_native_tool("run_python", {"path": "script.py"}, workspace,
                                  sandbox=SandboxExecutor(SandboxPolicy(), runner=forbidden))
    assert result["ok"] is False and result["execution"]["failure_origin"] == "environment"


def test_native_tool_routes_to_sandbox_and_returns_observed_failure(tmp_path):
    workspace = task_workspace(tmp_path)
    docker = DockerStub(exit_code=1)
    result = _execute_native_tool("run_python", {"path": "script.py"}, workspace,
                                  sandbox=SandboxExecutor(SandboxPolicy(image=IMAGE), runner=docker))
    assert result["ok"] is False and result["returncode"] == 1
    assert result["execution"]["failure_origin"] == "agent_execution"
    assert not (workspace / "outputs" / "result.txt").exists()


def test_timeout_force_removes_own_container_and_confirms_absence(tmp_path):
    workspace = task_workspace(tmp_path)
    docker = DockerStub(timeout=True)
    outcome = SandboxExecutor(SandboxPolicy(image=IMAGE), runner=docker).run(workspace / "script.py", workspace, 1)
    assert outcome.status == "timeout" and outcome.failure_origin == "agent_execution"
    assert docker.removed
    cleanup = json.loads((workspace / outcome.trace_refs[0]).read_text())["cleanup"]
    assert cleanup["confirmed_absent"] is True
    names = [cmd[-1] for cmd, _, _ in docker.calls if "rm" in cmd]
    assert len(names) == 1 and names[0].startswith("wrsi-")


def test_unconfirmed_cleanup_blocks_exports_and_future_execution(tmp_path):
    workspace = task_workspace(tmp_path)
    docker = DockerStub(cleanup_fails=True)
    executor = SandboxExecutor(SandboxPolicy(image=IMAGE), runner=docker)
    outcome = executor.run(workspace / "script.py", workspace, 1)
    assert outcome.status == "unavailable" and outcome.failure_origin == "environment"
    assert not (workspace / "outputs" / "result.txt").exists()
    count = len(docker.calls)
    assert executor.run(workspace / "script.py", workspace, 1).status == "unavailable"
    assert len(docker.calls) == count


@pytest.mark.parametrize("changes", [{"image": "python:latest"}, {"uid": 0}, {"pids_limit": 129},
                                     {"memory_bytes": 2147483649}, {"cpus": 2.1}, {"network": "host"},
                                     {"environment": {"SECRET": "dummy"}}])
def test_policy_cannot_weaken_required_boundary(changes):
    with pytest.raises(ValidationError):
        SandboxPolicy(**changes)


@pytest.mark.parametrize("mode", ["bad_output", "changed_input"])
def test_untrusted_exports_and_modified_staged_inputs_are_not_accepted(tmp_path, mode):
    workspace = task_workspace(tmp_path)
    docker = DockerStub(**{mode: True})
    outcome = SandboxExecutor(SandboxPolicy(image=IMAGE), runner=docker).run(workspace / "script.py", workspace, 1)
    assert outcome.status == "failed"
    assert not (workspace / "outputs" / "result.txt").exists()
    assert (workspace / "inputs" / "source.txt").read_text() == "source sentinel"


def test_symlink_input_and_output_parent_are_rejected_before_docker(tmp_path):
    workspace = task_workspace(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (workspace / "outputs").symlink_to(outside, target_is_directory=True)
    except OSError:
        # Windows junctions require no symlink privilege; keep this test active.
        completed = subprocess.run(["cmd", "/c", "mklink", "/J", str(workspace / "outputs"), str(outside)], capture_output=True)
        assert completed.returncode == 0
    docker = DockerStub()
    outcome = SandboxExecutor(SandboxPolicy(image=IMAGE), runner=docker).run(workspace / "script.py", workspace, 1)
    assert outcome.status == "failed" and not docker.calls
    assert list(outside.iterdir()) == []


def test_provider_capabilities_keep_cli_boundary_separate():
    cli = CodexOfficeProvider(WorkAgentConfig())
    assert cli.execution_capabilities()["backend"] == "codex-cli-workspace-write"
    assert cli.execution_capabilities()["t04_qualified"] is False
    native = CodexOfficeProvider(WorkAgentConfig(backend="openai-chat"))
    assert native.execution_capabilities()["backend"] == "docker"


def test_bounded_client_transport_drains_large_output_without_unbounded_retention():
    result = _docker_run([sys.executable, "-c", "import sys; sys.stdout.write('x'*1000000+'END'); sys.stderr.write('y'*1000000+'ERR')"],
                         10, {key: os.environ[key] for key in ("PATH", "SystemRoot", "WINDIR") if key in os.environ})
    assert result.returncode == 0
    assert len(result.stdout) == len(result.stderr) == 20000
    assert result.stdout.endswith("END") and result.stderr.endswith("ERR")


@pytest.mark.parametrize("problem", ["missing_cli", "windows_engine", "missing_image", "wrong_digest"])
def test_probe_rejects_unavailable_or_wrong_runtime_identity(problem):
    def transport(command, timeout, env):
        if problem == "missing_cli":
            raise FileNotFoundError("authored missing docker")
        if "info" in command:
            return subprocess.CompletedProcess(command, 0, json.dumps({"OSType": "windows" if problem == "windows_engine" else "linux"}), "")
        return subprocess.CompletedProcess(command, 1 if problem == "missing_image" else 0,
                                           json.dumps([{"Os": "linux", "Id": IMAGE_ID, "RepoDigests": []}]), "")
    result = SandboxExecutor(SandboxPolicy(image=IMAGE), runner=transport).probe()
    assert result["status"] == "unavailable" and result["t04_qualified"] is False


def test_local_content_addressed_image_needs_no_registry_push():
    policy = SandboxPolicy(image=IMAGE_ID)
    assert SandboxExecutor(policy, runner=DockerStub()).probe()["status"] == "available"


def test_native_api_stops_after_unavailable_sandbox_without_another_model_call(tmp_path, monkeypatch):
    workspace = task_workspace(tmp_path)
    requests = []
    def offline_transport(request, timeout):
        requests.append(request)
        payload = {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": "dummy-call", "type": "function", "function": {"name": "run_python", "arguments": '{"path":"script.py"}'}}
        ]}}]}
        return io.BytesIO(json.dumps(payload).encode())
    monkeypatch.setenv("WRSI_TEST_DUMMY_KEY", "dummy-only")
    monkeypatch.setattr("workagent_rsi.workagent_provider.urllib.request.urlopen", offline_transport)
    provider = CodexOfficeProvider(WorkAgentConfig(backend="openai-chat", api_key_env="WRSI_TEST_DUMMY_KEY",
                                                  api_base_url="https://offline.invalid/v1", verify_com=False))
    outcome = provider.run("authored offline test", workspace, tmp_path / "records")
    assert outcome.status == "unavailable" and len(requests) == 1
    assert "no host fallback" in outcome.error
