"""Bounded task-only SSH transport to an existing Apptainer + systemd user host."""
from __future__ import annotations
import base64
import json
from pathlib import Path
import shlex
import subprocess
import time
from typing import Literal
from uuid import uuid4

from pydantic import Field, field_validator

from .execution_sandbox import SandboxPolicy, _no_links, _inventory
from .hashing import sha256_file
from .run_contracts import ExecutionOutcome, RunUsage


class ApptainerPolicy(SandboxPolicy):
    backend: Literal["apptainer-ssh"] = "apptainer-ssh"
    image: None = None
    ssh_host: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
    uid: int = Field(ge=1)
    gid: int = Field(ge=1)
    remote_image: str
    remote_image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    apptainer_executable: str = "/usr/bin/apptainer"
    python_executable: str = "/usr/bin/python3"
    max_total_bytes: int = Field(default=33554432, ge=1, le=33554432)

    @field_validator("remote_image", "apptainer_executable", "python_executable")
    @classmethod
    def absolute_remote_paths(cls, value):
        if not value.startswith("/") or any(x in value for x in ("\n", "\r", ",", ":", "\\")) or ".." in value.split("/"):
            raise ValueError("remote runtime paths must be absolute and unambiguous")
        return value


def _ssh_request(policy: ApptainerPolicy, request: dict) -> dict:
    worker = Path(__file__).with_name("apptainer_worker.py").read_text(encoding="utf-8")
    command = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", policy.ssh_host,
               "/usr/bin/python3 -c " + shlex.quote(worker)]
    # Worker bounds file transfer and drains script stdout/stderr into fixed tails.
    result = subprocess.run(command, input=json.dumps(request), capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=request.get("timeout_seconds", 10)+45)
    if result.returncode:
        raise OSError("SSH worker unavailable; no generated code executed locally")
    return json.loads(result.stdout)


class ApptainerSSHExecutor:
    def __init__(self, policy: ApptainerPolicy, *, transport=_ssh_request, authored_boundary_probe: bool = False):
        self.policy, self.transport = policy, transport
        self.authored_boundary_probe = authored_boundary_probe
        self._cleanup_blocked = False

    def probe(self):
        if self._cleanup_blocked:
            return {"status": "unavailable", "reason": "prior remote cleanup unconfirmed", "t04_qualified": False}
        try:
            return self.transport(self.policy, {"action": "probe", "policy": self.policy.model_dump(mode="json")})
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return {"status": "unavailable", "reason": "SSH/Apptainer/runtime probe failed", "t04_qualified": False}

    def run(self, script: Path, workspace: Path, timeout_seconds: int) -> ExecutionOutcome:
        started = time.monotonic()
        status, origin, refs, trace_ref = "unavailable", "environment", [], None
        record = {"backend": "apptainer-ssh", "policy": self.policy.model_dump(mode="json"), "t04_qualified": False}
        try:
            if self._cleanup_blocked:
                raise OSError("prior remote cleanup unconfirmed; executor quarantined")
            root, script = _no_links(Path(workspace)), _no_links(Path(script))
            relative = script.relative_to(root).as_posix()
            if script.suffix != ".py" or relative.split("/")[0] in {"inputs", "outputs", "scratch", ".git", "provider_records"}:
                raise ValueError("invalid script location")
            if script.stat().st_nlink != 1 or script.stat().st_size > self.policy.max_file_bytes:
                raise ValueError("invalid script size/link count")
            _no_links(root / "provider_records/sandbox")
            trace_ref = "provider_records/sandbox/" + uuid4().hex + ".json"
            sources = {relative: sha256_file(script)}
            for name in ("inputs", "outputs", "scratch"):
                sources.update({name + "/" + file: digest for file,digest in _inventory(root / name, self.policy).items()})
            if len(sources) > 384 or sum((root / name).stat().st_size for name in sources) > 67108864:
                raise ValueError("SSH transfer budget exceeded")
            files = {name: {"sha256": digest, "data": base64.b64encode((root / name).read_bytes()).decode()}
                     for name,digest in sources.items()}
            result = self.transport(self.policy, {"action": "run", "policy": self.policy.model_dump(mode="json"),
                                                   "script": relative, "timeout_seconds": timeout_seconds, "files": files,
                                                   "authored_boundary_probe": self.authored_boundary_probe})
            record.update({key: value for key,value in result.items() if key != "files"})
            if not result.get("cleanup", {}).get("confirmed_absent"):
                self._cleanup_blocked = True
                record["error"] = "remote cleanup unconfirmed; no exports; executor quarantined"
            else:
                status, origin = result["status"], result.get("failure_origin")
                if status == "succeeded":
                    if any(sha256_file(_no_links(root / name)) != digest for name,digest in sources.items()):
                        raise ValueError("local source files changed during execution")
                    # Decode and check every file before writing any user-visible export.
                    exports, total = {}, 0
                    for name,data in result.get("files", {}).items():
                        parts = name.split("/")
                        if (parts[0] not in {"outputs", "scratch"} or len(parts)<2 or "\\" in name or ":" in name
                                or any(p in {"", ".", ".."} for p in parts)):
                            raise ValueError("unsafe remote export")
                        destination = _no_links(root / name)
                        content = base64.b64decode(data["data"], validate=True)
                        import hashlib
                        total += len(content)
                        if (hashlib.sha256(content).hexdigest() != data["sha256"] or len(content) > self.policy.max_file_bytes
                                or total > self.policy.max_total_bytes or len(exports) >= self.policy.max_files*2):
                            raise ValueError("remote export hash/budget mismatch")
                        if destination.exists() and not destination.is_file():
                            raise ValueError("remote export destination is not a file")
                        exports[name] = content
                    for name,content in exports.items():
                        destination = _no_links(root / name)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(content)
                    refs = [name for name in exports if name.startswith("outputs/")]
            record.pop("files", None)  # Binary bodies belong to artifacts, not the trace.
        except ValueError as exc:
            status, origin = "failed", "agent_execution"
            record["error"] = str(exc)
        except (OSError, subprocess.TimeoutExpired, KeyError, TypeError) as exc:
            status, origin = "unavailable", "environment"
            self._cleanup_blocked = True
            record["error"] = "remote infrastructure unavailable: " + type(exc).__name__
        outcome = ExecutionOutcome(status=status, failure_origin=origin, artifact_refs=refs,
                                   trace_refs=[trace_ref] if trace_ref else [],
                                   usage=RunUsage(wall_seconds=time.monotonic()-started, statuses={"wall_seconds": "available"}))
        record["outcome"] = outcome.model_dump(mode="json")
        if trace_ref:
            path = _no_links(root / trace_ref)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as stream:
                json.dump(record, stream, ensure_ascii=False, indent=2)
        return outcome
