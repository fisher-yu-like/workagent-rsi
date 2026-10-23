"""Trusted SSH worker. Generated scripts execute only inside Apptainer.

This file is sent as a Python program, not installed on the server. JSON stdin
contains only selected task files. User services bound the entire process tree.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import stat
import subprocess
import tempfile
import threading
import time
from uuid import uuid4


def fingerprint(root):
    """Include symlink targets without traversing them in a trusted runtime tree."""
    digest = hashlib.sha256()
    count, size = 0, 0
    for directory, folders, files in os.walk(root, followlinks=False):
        for name in sorted(folders + files):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            info = path.lstat()
            digest.update((relative + "\0" + oct(stat.S_IMODE(info.st_mode)) + "\0").encode())
            if path.is_symlink():
                digest.update(("link:" + os.readlink(path)).encode())
            elif path.is_file():
                count += 1
                size += info.st_size
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1048576), b""):
                        digest.update(chunk)
            elif not path.is_dir():
                raise ValueError("runtime contains a non-file object")
            digest.update(b"\0")
        folders.sort()
    return digest.hexdigest(), count, size


def relative_path(name):
    if (not isinstance(name, str) or not name or "\\" in name or ":" in name
            or name.startswith("/") or any(p in {"", ".", ".."} for p in name.split("/"))):
        raise ValueError("unsafe task file reference")
    return PurePosixPath(name)


def regular_files(root, limit, max_bytes):
    result = {}
    total = 0
    for directory, folders, files in os.walk(root, followlinks=False):
        for name in folders:
            if (Path(directory) / name).is_symlink():
                raise ValueError("output directory is a symlink")
        for name in sorted(files):
            path = Path(directory) / name
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("output must be a single-link regular file")
            total += info.st_size
            if total > max_bytes or len(result) >= limit:
                raise ValueError("remote output budget exceeded")
            result[path.relative_to(root).as_posix()] = path
    return result


def main(request):
    uid = os.getuid()
    policy = request["policy"]
    image = Path(policy["remote_image"])
    executable = policy["apptainer_executable"]
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp",
           "XDG_RUNTIME_DIR": f"/run/user/{uid}",
           "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{uid}/bus"}

    def command(args, timeout=10):
        return subprocess.run(args, env=env, capture_output=True, text=True, timeout=timeout)

    identity, image_files, image_bytes = fingerprint(image)
    if identity != policy["remote_image_sha256"]:
        raise ValueError("runtime fingerprint mismatch")
    version = command([executable, "--version"])
    if (version.returncode or uid != policy["uid"] or os.getgid() != policy["gid"] or uid == 0
            or not Path(env["XDG_RUNTIME_DIR"], "bus").is_socket()):
        raise ValueError("nonroot Apptainer/user D-Bus runtime unavailable")
    capability = {"status": "available", "version": version.stdout.strip(), "uid": uid,
                  "image_sha256": identity, "image_files": image_files, "image_bytes": image_bytes,
                  "t04_qualified": False}
    if request["action"] == "probe":
        return capability
    timeout = request["timeout_seconds"]
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise ValueError("invalid deadline")
    memory, pids, cpus = policy["memory_bytes"], policy["pids_limit"], policy["cpus"]
    if not (67108864 <= memory <= 2147483648 and 1 <= pids <= 128 and 0 < cpus <= 2):
        raise ValueError("invalid resource policy")
    unit = "wrsi-" + uuid4().hex + ".service"
    stage = Path(tempfile.mkdtemp(prefix="wrsi-task-"))
    response = {"capability": capability, "unit": unit, "status": "unavailable", "failure_origin": "environment",
                "stdout": "", "stderr": "", "returncode": None, "files": {}, "cleanup": {"confirmed_absent": False}}
    launched = False
    try:
        (stage / "task/inputs").mkdir(parents=True)
        for name in ("outputs", "scratch"):
            (stage / name).mkdir()
            (stage / "task" / name).mkdir()
        total = 0
        files = request["files"]
        if len(files) > 384:
            raise ValueError("too many remote input files")
        for name, data in files.items():
            relative_path(name)
            content = base64.b64decode(data["data"], validate=True)
            total += len(content)
            if total > 67108864 or hashlib.sha256(content).hexdigest() != data["sha256"]:
                raise ValueError("remote input budget/hash mismatch")
            first, *rest = name.split("/")
            destination = stage / name if first in {"outputs", "scratch"} else stage / "task" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        script = str(relative_path(request["script"]))
        if script.split("/")[0] in {"inputs", "outputs", "scratch", ".git", "provider_records"} or not script.endswith(".py"):
            raise ValueError("invalid remote script")
        before = {name: hashlib.sha256((stage / "task" / name).read_bytes()).hexdigest()
                  for name in files if name.split("/")[0] not in {"outputs", "scratch"}}
        # ExecStartPre runs before untrusted code. Its report lives outside all
        # container mounts, so the task cannot forge the observed cgroup limits.
        guard = stage / "guard.py"
        guard.write_text('''import json,os
from pathlib import Path
group=next(line.split(':',2)[2].strip() for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
root=Path('/sys/fs/cgroup')/group.lstrip('/')
memory=(root/'memory.max').read_text().strip()
swap=(root/'memory.swap.max').read_text().strip()
pids=(root/'pids.max').read_text().strip()
cpu=(root/'cpu.max').read_text().split()
facts={'cgroup':group,'memory_max':memory,'memory_swap_max':swap,'pids_max':pids,'cpu_max':cpu,'uid':os.getuid()}
facts['passed']=(memory!='max' and 0<int(memory)<=MEMORY and swap=='0' and pids!='max' and 0<int(pids)<=PIDS and cpu[0]!='max' and int(cpu[0])/int(cpu[1])<=CPUS and group.endswith('/UNIT') and os.getuid()==UID)
Path(REPORT).write_text(json.dumps(facts))
raise SystemExit(0 if facts['passed'] else 1)
'''.replace('MEMORY', str(memory)).replace('PIDS', str(pids)).replace('CPUS', repr(cpus))
            .replace('UNIT', unit).replace('UID', str(uid)).replace('REPORT', repr(str(stage / "guard.json"))))
        args = ["systemd-run", "--user", "--wait", "--pipe", "--quiet", "--unit=" + unit,
                "--property=ExecStartPre=/usr/bin/python3 " + str(guard),
                f"--property=MemoryMax={memory}", "--property=MemorySwapMax=0",
                f"--property=TasksMax={pids}", f"--property=CPUQuota={int(cpus*100)}%",
                f"--property=RuntimeMaxSec={timeout}", "--property=KillMode=control-group",
                f"--property=LimitFSIZE={policy['max_total_bytes']}",
                "--property=TimeoutStopSec=2", "/usr/bin/env", "-i",
                "PATH=" + str(Path(executable).parent) + ":/usr/local/bin:/usr/bin:/bin", "HOME=/tmp",
                "XDG_RUNTIME_DIR=" + env["XDG_RUNTIME_DIR"],
                "DBUS_SESSION_BUS_ADDRESS=" + env["DBUS_SESSION_BUS_ADDRESS"], executable, "exec",
                "--containall", "--cleanenv", "--no-home", "--no-mount", "home,cwd,hostfs,bind-paths",
                "--net", "--network", "none", "--no-privs", "--drop-caps", "ALL", "--pwd", "/task"]
        if request.get("authored_boundary_probe") is True:
            (stage / "host-sentinel.txt").write_text("authored-remote-parent-only")
            args.insert(1, "--setenv=WRSI_PROBE_DUMMY_SECRET=authored-dummy-only")
        for source, target, mode in ((stage / "task", "/task", "ro"), (stage / "outputs", "/task/outputs", "rw"),
                                      (stage / "scratch", "/task/scratch", "rw")):
            args.extend(["--bind", f"{source}:{target}:{mode}"])
        args.extend([str(image), "/bin/env", "-i", "PATH=/usr/local/bin:/usr/bin:/bin", "HOME=/tmp", "TMPDIR=/tmp",
                     policy["python_executable"], "-I", "-B", "/task/" + script])
        if request.get("authored_boundary_probe") is True:
            args.append(str(stage / "host-sentinel.txt"))
        response["command"] = args
        process = subprocess.Popen(args, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        launched = True
        buffers = [bytearray(), bytearray()]
        def drain(stream, buffer):
            for chunk in iter(lambda: stream.read(4096), b""):
                buffer.extend(chunk)
                del buffer[:-20000]
            stream.close()
        threads = [threading.Thread(target=drain, args=(s,b), daemon=True)
                   for s,b in zip((process.stdout, process.stderr), buffers)]
        for thread in threads: thread.start()
        expired = False
        try:
            process.wait(timeout=timeout+5)
        except subprocess.TimeoutExpired:
            expired = True
            command(["systemctl", "--user", "stop", unit], timeout=10)
            process.kill()
            process.wait(timeout=5)
        for thread in threads: thread.join(timeout=5)
        response["stdout"], response["stderr"] = (bytes(b).decode("utf-8", errors="replace") for b in buffers)
        facts = command(["systemctl", "--user", "show", unit, "--property=Result", "--property=ExecMainStatus",
                         "--property=MemoryMax", "--property=MemorySwapMax", "--property=TasksMax",
                         "--property=CPUQuotaPerSecUSec", "--property=ControlGroup", "--property=KillMode"])
        properties = dict(line.split("=",1) for line in facts.stdout.splitlines() if "=" in line)
        response["systemd_post_exit_properties"] = properties
        guard_report = json.loads((stage / "guard.json").read_text()) if (stage / "guard.json").is_file() else {}
        response["resource_observations"] = guard_report
        response["returncode"] = int(properties.get("ExecMainStatus", process.returncode))
        response["status"] = "timeout" if expired or properties.get("Result") == "timeout" else (
            "succeeded" if process.returncode == 0 and properties.get("Result") == "success" else "failed")
        response["failure_origin"] = None if response["status"] == "succeeded" else "agent_execution"
        if not guard_report.get("passed"):
            response.update(status="unavailable", failure_origin="environment", error="required cgroup limits not observed before execution")
        if any(hashlib.sha256((stage / "task" / name).read_bytes()).hexdigest() != value for name, value in before.items()):
            raise ValueError("staged source input integrity changed")
        if response["status"] == "succeeded":
            for name in ("outputs", "scratch"):
                for relative, path in regular_files(stage / name, policy["max_files"], policy["max_total_bytes"]).items():
                    content = path.read_bytes()
                    response["files"][name + "/" + relative] = {
                        "sha256": hashlib.sha256(content).hexdigest(), "data": base64.b64encode(content).decode()}
    except ValueError as exc:
        response.update(status="failed", failure_origin="agent_execution", files={}, error=str(exc))
    finally:
        if launched:
            command(["systemctl", "--user", "stop", unit])
            command(["systemctl", "--user", "reset-failed", unit])
            state = command(["systemctl", "--user", "show", unit, "--property=ActiveState", "--property=LoadState"])
            absent = "ActiveState=inactive" in state.stdout and "LoadState=not-found" in state.stdout
            group = response.get("resource_observations", {}).get("cgroup")
            descendants_gone = True
            if group:
                processes = Path('/sys/fs/cgroup') / group.lstrip('/') / 'cgroup.procs'
                descendants_gone = not processes.exists() or not processes.read_text().strip()
            response["cleanup"] = {"confirmed_absent": absent and descendants_gone, "unit": unit,
                                   "cgroup_empty_or_removed": descendants_gone}
            absent = absent and descendants_gone
            if not absent:
                response.update(status="unavailable", failure_origin="environment", files={}, quarantined_stage=str(stage))
        else:
            response["cleanup"] = {"confirmed_absent": True, "unit_not_created": True}
        if response["cleanup"]["confirmed_absent"]:
            shutil.rmtree(stage)
    if fingerprint(image)[0] != identity:
        raise ValueError("runtime identity changed during execution")
    return response


if __name__ == "__main__":
    try:
        request = json.load(__import__("sys").stdin)
        result = main(request)
    except Exception as exc:
        result = {"status": "unavailable", "failure_origin": "environment", "error": type(exc).__name__ + ": " + str(exc),
                  "t04_qualified": False}
    print(json.dumps(result, separators=(",", ":")))
