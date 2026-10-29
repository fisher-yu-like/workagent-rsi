# T04 execution runtimes

Generated Python from native API tools runs only through an explicitly configured
runtime. Missing runtime/image, mismatched identity, or unconfirmed cleanup
blocks execution; there is no host-Python fallback. Codex CLI's own
`workspace-write` sandbox is a separate capability and does not qualify T04.

## Docker (default backend)

Use a local Linux container engine. Provisioning is explicit and is never done
inside an agent run. `Dockerfile` has no default base: supply an approved immutable
`python:3.13-slim-bookworm@sha256:...` base. `requirements.lock` pins official
Linux x86_64 CPython 3.13 wheels and hashes. The image build has **not** been run
on the current Windows computer or on the supplied cluster.

```powershell
# Provisioning commands, not automatically executed by WorkAgent-RSI:
docker build --build-arg PYTHON_BASE=<approved-python-reference-with-sha256> --iidfile runtime-image.id deploy/agent-runtime
```

Use the exact local `sha256:...` content ID from the build, or an already-local
`repository@sha256:...` reference. Tags alone are rejected. No push is required
for a local content ID. Runtime requests use the local engine, an empty Docker
configuration, and `--pull=never`. Only isolated copies of the script and
`inputs/` are mounted read-only; `outputs/` and `scratch/` have separate writable
mounts. Runtime code writes to these two directories, not the workspace root.
The network is disabled; root filesystem is read-only; privileges, processes,
CPU and memory are restricted. Docker removal targets only the UUID owned by
this invocation and confirms absence before exports.

```json
{
  "backend": "docker",
  "image": "sha256:<64 lowercase hex digits>"
}
```

## Existing Apptainer server through SSH

The alternate `apptainer-ssh` backend uses an existing SSH alias, existing
Apptainer installation, and a frozen private runtime directory. It sends only
selected task files, not the repository, HOME, provider records, hidden data or
credentials. API requests stay on the caller. The remote trusted worker runs as
a short-lived Python program over SSH and is not installed on the server.

Apptainer uses `--containall`, `--cleanenv`, `--no-home`, explicit automatic-mount
exclusions, `--net --network none`, and no capabilities. A unique systemd user
service provides aggregate memory, CPU and PID limits, a deadline, and
`KillMode=control-group`. A trusted `ExecStartPre` guard reads actual cgroup
limits before any generated code starts; its report is outside all container
mounts. Cleanup stops only the owned unit and checks both the unit and its
cgroup before exports. A failed cleanup quarantines that executor instance.
Unavailable SSH/systemd/Apptainer never switches to local execution.

The current server's noninteractive SSH sessions require the existing user bus
at `/run/user/<uid>/bus`; the worker supplies its address without changing system
settings. This backend requires cgroup v2 and a functioning systemd user manager.

```json
{
  "backend": "apptainer-ssh",
  "ssh_host": "<existing-ssh-alias>",
  "uid": 1001,
  "gid": 1001,
  "remote_image": "/absolute/path/to/private-runtime-rootfs",
  "remote_image_sha256": "<64 lowercase hex digits>",
  "apptainer_executable": "/absolute/path/to/apptainer",
  "python_executable": "/usr/bin/python3"
}
```

`remote_image_sha256` fingerprints the runtime tree, including file modes,
contents and symlink targets, before and after each execution. Compute it with
the `fingerprint` function in `apptainer_worker.py` on the runtime host; it is not
the source SIF checksum. The provisioning record separately retains source SIF
and wheel hashes. A changed/missing runtime must be provisioned and qualified
again. `/tmp` runtimes can disappear after host cleanup or reboot.

For the supplied cluster we reused existing SIF files and extracted only Python
and required system libraries into a new private directory. Nine official PyPI
wheels totaled 14,168,107 bytes; they were hash-verified and extracted into that
directory, not installed in host Python. No new container image was downloaded,
no administrator settings were changed, and no model was called. The source
image's application, Git repository and caches were excluded.

`prepare_apptainer_runtime.py --help` describes the explicit provisioner. It
requires a new destination, existing source and BusyBox seed SIF files, verified
SIF offsets, and a wheelhouse with `manifest.json` (name, filename, size, sha256,
source, version). It assumes Debian CPython 3.11 source layout and must be
validated after preparation; it is not a general converter for arbitrary images.
Inspect SIF offsets with `apptainer sif list`, and provide wheels for the actual
Python ABI, not the CPython 3.13 Docker lock. Failed provision attempts and their
records are retained. The current frozen runtime and qualified policy are in
the T04 result manifest, not silently selected as a global default.

## Offline checks and explicit real probes

```powershell
$TaskPython = '.\.venv\Scripts\python.exe'
& $TaskPython project_artifacts/phase3_experiments/scripts/run_hardening_checks.py T04 tests/test_execution_sandbox.py tests/test_apptainer_sandbox.py tests/test_workagent_provider.py
& $TaskPython project_artifacts/phase3_experiments/scripts/probe_execution_sandbox.py --help
# Capability only by default; --execute is required for authored probe scripts:
& $TaskPython project_artifacts/phase3_experiments/scripts/probe_execution_sandbox.py --policy <sandbox-policy.json> --execute
```

Each probe creates a new evidence directory. It tests parent sentinels, dummy
environment isolation, network namespace and connection denial, source/root
read-only behavior, nonroot privileges, actual resource observations, real
XLSX/DOCX/PPTX generation and library reopening, and cleanup of an independently
sessioned child after timeout. These are authored engineering probes, not model
performance, COM/visual/Office-worker qualification or an RSI result. Native
Docker qualification remains separate from Apptainer qualification.

Construct `WorkAgentConfig(sandbox_policy=<parsed-policy>, backend="openai-chat")`
and pass it as `Harness(workagent_config=config)` when a future authorized run
needs this backend. This configuration does not authorize model calls. T03's
default-off `LiveCallPolicy` is an additive approval contract; full reservations
and live qualification remain T22/T31 work.

Input/export counts and bytes are bounded, and Apptainer has a per-file write
limit. These checks are not a filesystem-wide disk quota. Only small authored
probes ran on the server with the user's 4 GB storage constraint; future large
tasks need a suitable scratch quota. T05 must still supply authorized input
views and Office rendering boundaries; T04 does not decide which task inputs
are semantically authorized.

Runtime options follow the primary references:
[Docker run](https://docs.docker.com/reference/cli/docker/container/run/),
[Apptainer exec](https://apptainer.org/docs/user/main/cli/apptainer_exec.html).
