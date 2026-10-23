"""One-shot Docker execution. No image/runtime means no generated-code execution.

Only staged inputs and the selected script are mounted read-only. Docker is
contacted through the local engine, never through inherited contexts/credentials.
Unit transports do not establish an OS boundary; qualification requires probes.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import threading
import time
from typing import Literal
from uuid import uuid4

from pydantic import Field

from .hashing import sha256_file
from .run_contracts import ExecutionOutcome, RunContract, RunUsage


class SandboxPolicy(RunContract):
    backend: Literal["docker"] = "docker"
    image: str | None = Field(default=None, pattern=r"^(?:sha256:[0-9a-f]{64}|[a-zA-Z0-9][a-zA-Z0-9./:_-]*@sha256:[0-9a-f]{64})$")
    network: Literal["none"] = "none"
    uid: int = Field(default=65532, ge=1)
    gid: int = Field(default=65532, ge=1)
    pids_limit: int = Field(default=128, ge=1, le=128)
    memory_bytes: int = Field(default=2147483648, ge=67108864, le=2147483648)
    cpus: float = Field(default=2.0, gt=0, le=2)
    max_files: int = Field(default=128, ge=1, le=1024)
    max_file_bytes: int = Field(default=104857600, ge=1, le=104857600)
    max_total_bytes: int = Field(default=268435456, ge=1, le=536870912)


DockerRunner = Callable[[list[str], float, dict[str, str]], subprocess.CompletedProcess]


def _docker_run(command: list[str], timeout: float, env: dict[str, str]) -> subprocess.CompletedProcess:
    """Drain both streams while retaining only a bounded tail in host memory."""
    process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    buffers = [bytearray(), bytearray()]

    def drain(stream, buffer):
        try:
            while chunk := stream.read(4096):
                buffer.extend(chunk)
                del buffer[:-20000]
        finally:
            stream.close()

    threads = [threading.Thread(target=drain, args=(stream, buffer), daemon=True)
               for stream, buffer in zip((process.stdout, process.stderr), buffers)]
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        process.wait(timeout=10)
    for thread in threads:
        thread.join(timeout=10)
    stdout, stderr = (bytes(buffer).decode("utf-8", errors="replace") for buffer in buffers)
    if timed_out:
        raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr)
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _no_links(path: Path) -> Path:
    path = path.absolute()
    for part in (*reversed(path.parents), path):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if (stat.S_ISLNK(info.st_mode)
                    or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                raise ValueError("symlink/reparse points are not permitted")
    return path


def _inventory(root: Path, policy: SandboxPolicy) -> dict[str, str]:
    _no_links(root)
    result = {}
    total = 0
    if not root.exists():
        return result
    for path in sorted(root.rglob("*")):
        _no_links(path)
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("only regular files with a single link may be staged/exported")
        total += info.st_size
        if (len(result) >= policy.max_files or info.st_size > policy.max_file_bytes
                or total > policy.max_total_bytes):
            raise ValueError("sandbox file/byte budget exceeded")
        result[path.relative_to(root).as_posix()] = sha256_file(path)
    return result


def _copy_files(source: Path, destination: Path, inventory: dict[str, str], *, writable: bool):
    destination.mkdir(parents=True, exist_ok=True)
    for relative, digest in inventory.items():
        path = _no_links(source / relative)
        if sha256_file(path) != digest:
            raise ValueError("file changed while preparing sandbox")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        target.chmod(0o666 if writable else 0o444)
    for path in [destination, *destination.rglob("*")]:
        if path.is_dir():
            path.chmod(0o777 if writable else 0o755)


class SandboxExecutor:
    def __init__(self, policy: SandboxPolicy | None = None, *, runner: DockerRunner = _docker_run,
                 executable: str = "docker"):
        self.policy = policy or SandboxPolicy()
        self.runner = runner
        self.executable = executable
        self.local_host = "npipe:////./pipe/docker_engine" if os.name == "nt" else "unix:///var/run/docker.sock"
        self._cleanup_blocked = False
        self._quarantined_stages: list[str] = []

    def _client_env(self, directory: Path) -> dict[str, str]:
        directory.mkdir(parents=True, exist_ok=True)
        env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "WINDIR") if key in os.environ}
        env.update(DOCKER_CONFIG=str(directory), HOME=str(directory), USERPROFILE=str(directory),
                   TMP=str(directory), TEMP=str(directory))
        return env

    def _call(self, args, env, timeout=10):
        return self.runner([self.executable, "--host", self.local_host, *args], max(.01, timeout), env)

    def _probe(self, env: dict[str, str], timeout: float = 10) -> dict:
        if self._cleanup_blocked:
            return {"status": "unavailable", "reason": "prior container cleanup unconfirmed; executor quarantined", "t04_qualified": False}
        if self.policy.image is None:
            return {"status": "unavailable", "reason": "immutable sandbox image is not configured", "t04_qualified": False}
        try:
            info = self._call(["info", "--format", "{{json .}}"], env, timeout)
            if info.returncode:
                return {"status": "unavailable", "reason": "local Docker engine unavailable", "t04_qualified": False}
            engine = json.loads(info.stdout)
            if engine.get("OSType") != "linux":
                return {"status": "unavailable", "reason": "Linux container engine required", "t04_qualified": False}
            image = self._call(["image", "inspect", self.policy.image], env, timeout)
            if image.returncode:
                return {"status": "unavailable", "reason": "approved image not present locally; automatic pull disabled", "t04_qualified": False}
            identity = json.loads(image.stdout)[0]
            matches = (self.policy.image == identity.get("Id") if self.policy.image.startswith("sha256:")
                       else self.policy.image in (identity.get("RepoDigests") or []))
            if (identity.get("Os") != "linux" or not matches
                    or not str(identity.get("Id", "")).startswith("sha256:")):
                return {"status": "unavailable", "reason": "image identity/OS mismatch", "t04_qualified": False}
            return {"status": "available", "image": self.policy.image, "image_id": identity["Id"],
                    "engine_version": engine.get("ServerVersion"), "t04_qualified": False}
        except (OSError, subprocess.TimeoutExpired, ValueError, IndexError, TypeError):
            return {"status": "unavailable", "reason": "Docker CLI/engine/image probe failed", "t04_qualified": False}

    def probe(self) -> dict:
        with tempfile.TemporaryDirectory(prefix="wrsi-client-") as directory:
            return self._probe(self._client_env(Path(directory)))

    def create_command(self, name: str, stage: Path, script_relative: str) -> list[str]:
        """Explicit fixed options; callers cannot inject additional mounts or env."""
        p = self.policy
        command = ["create", "--name", name, "--label", "workagent-rsi.owner=" + name,
                   "--pull=never", "--network=none", "--read-only", "--cap-drop=ALL",
                   "--security-opt=no-new-privileges", "--user", f"{p.uid}:{p.gid}",
                   f"--pids-limit={p.pids_limit}", f"--memory={p.memory_bytes}",
                   f"--memory-swap={p.memory_bytes}", f"--cpus={p.cpus}", "--init",
                   "--ipc=private", "--log-driver=local", "--log-opt=max-size=1m", "--log-opt=max-file=1",
                   "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=67108864,mode=1777",
                   "--workdir", "/task", "--entrypoint", "/usr/bin/env"]
        for source, target, readonly in ((stage / "task", "/task", True),
                                         (stage / "outputs", "/task/outputs", False),
                                         (stage / "scratch", "/task/scratch", False)):
            if "," in str(source):
                raise ValueError("Docker mount source cannot contain commas")
            command.extend(["--mount", f"type=bind,source={source},target={target}" + (",readonly" if readonly else "")])
        command.extend([p.image, "-i", "PATH=/usr/local/bin:/usr/bin:/bin", "HOME=/tmp", "TMPDIR=/tmp",
                        "LANG=C.UTF-8", "PYTHONDONTWRITEBYTECODE=1", "/usr/local/bin/python", "-I", "-B",
                        "/task/" + script_relative])
        return command

    def _cleanup(self, name, env) -> dict:
        try:
            removal = self._call(["rm", "--force", "--volumes", name], env)
            check = self._call(["inspect", "--format", "{{.Id}}", name], env)
            absent = check.returncode != 0 and any(s in check.stderr.lower() for s in ("no such object", "no such container"))
            return {"remove_exit_code": removal.returncode, "confirmed_absent": absent, "container": name}
        except (OSError, subprocess.TimeoutExpired):
            return {"confirmed_absent": False, "container": name}

    def run(self, script: Path, workspace: Path, timeout_seconds: int) -> ExecutionOutcome:
        started = time.monotonic()
        record = {"schema_version": "sandbox-execution-v1", "started_at": datetime.now(timezone.utc).isoformat(),
                  "policy": self.policy.model_dump(mode="json"), "backend": "docker", "t04_qualified": False,
                  "stdout": "", "stderr": "", "returncode": None, "cleanup": {"not_created": True}}
        status, origin, refs = "unavailable", "environment", []
        stage = Path(tempfile.mkdtemp(prefix="wrsi-exec-"))
        keep_stage = False
        trace_relative = None
        try:
            if type(timeout_seconds) is not int or timeout_seconds < 1:
                raise ValueError("timeout_seconds must be a positive integer")
            deadline = started + timeout_seconds
            root = _no_links(Path(workspace))
            script = _no_links(Path(script))
            relative = script.relative_to(root).as_posix()
            if not root.is_dir() or script.suffix != ".py" or not script.is_file():
                raise ValueError("script must be a regular Python file inside workspace")
            if relative.split("/")[0] in {"inputs", "outputs", "scratch", "provider_records", ".git"}:
                raise ValueError("script must be separate from protected inputs and runtime outputs")
            if script.stat().st_nlink != 1 or script.stat().st_size > self.policy.max_file_bytes:
                raise ValueError("invalid script link count or size")
            for name in ("inputs", "outputs", "scratch", "provider_records", "provider_records/sandbox"):
                _no_links(root / name)
            inputs = _inventory(root / "inputs", self.policy)
            previous = {name: _inventory(root / name, self.policy) for name in ("outputs", "scratch")}
            record["input_hashes"] = inputs
            record["script_sha256"] = sha256_file(script)
            trace_relative = f"provider_records/sandbox/{uuid4().hex}.json"
            # The whole workspace/repository is never mounted. Only these copies.
            task = stage / "task"
            task.mkdir()
            _copy_files(root / "inputs", task / "inputs", inputs, writable=False)
            for name in ("outputs", "scratch"):
                _copy_files(root / name, stage / name, previous[name], writable=True)
                (task / name).mkdir()
            _copy_files(root, task, {relative: record["script_sha256"]}, writable=False)
            record["staged_files"] = sorted(["inputs/" + name for name in inputs] + [relative])
            env = self._client_env(stage / "client")
            probe = self._probe(env, min(10, max(.01, deadline-time.monotonic())))
            record["probe"] = probe
            if probe["status"] != "available":
                record["error"] = probe["reason"]
            else:
                record["image_id"] = probe["image_id"]
                name = "wrsi-" + uuid4().hex
                command = self.create_command(name, stage, relative)
                record["command"] = [self.executable, "--host", self.local_host, *command]
                try:
                    if time.monotonic() >= deadline:
                        raise subprocess.TimeoutExpired(command, timeout_seconds)
                    created = self._call(command, env, min(10, deadline-time.monotonic()))
                    if created.returncode:
                        record["error"] = "Docker container creation failed"
                    else:
                        if time.monotonic() >= deadline:
                            raise subprocess.TimeoutExpired(command, timeout_seconds)
                        attached = self._call(["start", "--attach", name], env, deadline-time.monotonic())
                        record["stdout"], record["stderr"] = attached.stdout[-20000:], attached.stderr[-20000:]
                        inspected = self._call(["inspect", "--format", "{{json .State}}", name], env)
                        try:
                            state = json.loads(inspected.stdout) if inspected.returncode == 0 else {}
                        except ValueError:
                            state = {}
                        record["state"] = state
                        if state.get("Running") is not False or type(state.get("ExitCode")) is not int:
                            record["error"] = "container exit state could not be confirmed"
                        else:
                            record["returncode"] = state["ExitCode"]
                            status = "succeeded" if state["ExitCode"] == 0 and not state.get("OOMKilled") else "failed"
                            origin = None if status == "succeeded" else "agent_execution"
                except subprocess.TimeoutExpired:
                    status, origin = "timeout", "agent_execution"
                    record["error"] = "sandbox execution deadline exceeded"
                finally:
                    record["cleanup"] = self._cleanup(name, env)
                    if not record["cleanup"]["confirmed_absent"]:
                        self._cleanup_blocked = keep_stage = True
                        self._quarantined_stages.append(str(stage))
                        record["quarantined_stage"] = str(stage)
                        status, origin = "unavailable", "environment"
                        record["error"] = "container cleanup unconfirmed; no exports, executor quarantined"
                if status == "succeeded":
                    if (_inventory(task / "inputs", self.policy) != inputs
                            or _inventory(root / "inputs", self.policy) != inputs
                            or sha256_file(script) != record["script_sha256"]):
                        raise ValueError("source input/script integrity changed")
                    exported = {name: _inventory(stage / name, self.policy) for name in ("outputs", "scratch")}
                    # Preflight every destination before any export, including junctions.
                    for name, files in exported.items():
                        for file in files:
                            _no_links(root / name / file)
                    for name, files in exported.items():
                        _copy_files(stage / name, root / name, files, writable=True)
                    refs = ["outputs/" + file for file in exported["outputs"]]
                    record["exported_hashes"] = exported
        except ValueError as exc:
            status, origin = "failed", "agent_execution"
            record["error"] = str(exc)
        except (OSError, subprocess.TimeoutExpired, TypeError, KeyError) as exc:
            status, origin = "unavailable", "environment"
            record["error"] = "sandbox infrastructure error: " + type(exc).__name__
        finally:
            if not keep_stage:
                # Staged readonly files need their owner write bit on Windows.
                for path in stage.rglob("*"):
                    try:
                        _no_links(path)
                    except ValueError:
                        continue
                    if path.is_file():
                        path.chmod(0o600)
                shutil.rmtree(stage)
        usage = RunUsage(wall_seconds=time.monotonic()-started, statuses={"wall_seconds": "available"})
        outcome = ExecutionOutcome(status=status, failure_origin=origin, artifact_refs=refs,
                                   trace_refs=[trace_relative] if trace_relative else [], usage=usage)
        record["outcome"] = outcome.model_dump(mode="json")
        if trace_relative:
            trace = _no_links(root / trace_relative)
            trace.parent.mkdir(parents=True, exist_ok=True)
            with trace.open("x", encoding="utf-8") as stream:
                json.dump(record, stream, indent=2, ensure_ascii=False)
                stream.write("\n")
        return outcome
