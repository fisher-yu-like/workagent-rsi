# Controlled Office rendering (T05)

`OfficeArtifactRenderer` renders verified XLSX, DOCX and PPTX copies with
LibreOffice UNO and Poppler **inside an explicitly configured T04 sandbox**.
An unconfigured worker returns `unavailable`. The renderer never activates
Windows Office or runs host Poppler as a fallback.

The current qualified runtime is a private extracted Debian tree on
`cluster_vlab_jump`. It reuses the T04 Python runtime and adds Writer, Calc,
Impress, python3-uno, Poppler and DejaVu fonts. No host packages, maintainer
scripts or global Office settings are installed or changed.

## Run the authored infrastructure probes

Use an explicit Python environment from the repository root:

```powershell
& .\.venv\Scripts\python.exe -X utf8 project_artifacts/phase3_experiments/scripts/run_t05_office_probe.py --help
& .\.venv\Scripts\python.exe -X utf8 project_artifacts/phase3_experiments/scripts/run_t05_office_probe.py --policy <office-sandbox-policy.json> --process-checks
```

Every invocation creates a new evidence directory under
`project_artifacts/results/hardening-v2/T05/`. The fixtures are authored small
Office files, not external benchmark tasks. The optional process checks render
while a second owned Office sentinel remains alive, then exercise whole-service
timeout cleanup of a detached Office process. The sentinel is cleaned separately
by its creator. No user application participates in these checks.

The policy is an `ApptainerPolicy` JSON file. For this prepared environment:

```json
{
  "backend": "apptainer-ssh",
  "ssh_host": "cluster_vlab_jump",
  "uid": 68288,
  "gid": 68288,
  "remote_image": "/tmp/wrsi-t05-runtime-ngigwm0t/rootfs-office",
  "remote_image_sha256": "481af80d507540f293116f57b3331c75d5a69f55fa957c3643322fe471360cf7",
  "apptainer_executable": "/public/app/apptainer/1.4.5/bin/apptainer",
  "python_executable": "/usr/bin/python3"
}
```

The `/tmp` location is temporary. A missing tree, changed fingerprint, broken
SSH forwarding, unavailable cgroups or unconfirmed cleanup blocks execution.
Use the actual recorded identity, never change an expected hash merely to
bypass a failed check. See [T04 operations](../agent-runtime/README.md) for the
transport, resource constraints and explicit executor selection.

## Configure an evaluator explicitly

```python
import json
from pathlib import Path
from workagent_rsi.apptainer_sandbox import ApptainerPolicy, ApptainerSSHExecutor
from workagent_rsi.artifact_renderer import OfficeArtifactRenderer

policy = ApptainerPolicy.model_validate_json(Path("office-sandbox-policy.json").read_text())
renderer = OfficeArtifactRenderer(
    "project_artifacts/results/my-run/rendering",
    sandbox=ApptainerSSHExecutor(policy),
    timeout_seconds=90,
)
# Supply renderer=renderer to configured_assessment(...) when explicitly
# configuring model review, or to VisualAssessmentChannel directly.
```

The fixed render policy requires a hash-verified copy, a read-only input mount,
`ReadOnly=True`, `MacroExecutionMode=0` (never execute), `UpdateDocMode=0`
(no external updates), an aborting interaction handler, no network and an owned
worker. A unique UNO pipe and temporary profile prevent attaching to another
Office instance. One owned restart is permitted for LibreOffice's first-profile
exit code 81. Rendering closes only that document/desktop and reaps only its
tracked child. The T04 UUID service bounds and cleans all worker descendants.

The result records Office/Poppler binary hashes, versions, font and system
fingerprints. Renderer identity also includes worker code, DPI/page limits,
render policy and the sandbox/runtime identity. These identities distinguish
LibreOffice pagination and fonts from Microsoft Office output.

## Prepare a private runtime

`provision_apptainer_office.py` runs on the server alongside the trusted
`apptainer_worker.py` fingerprint helper. Supply an explicit package plan built
from signed Debian apt metadata, a verified base runtime and a new destination.
It verifies HTTPS package archive checksums, extracts bytes without executing
maintainer scripts, materializes the shipped LibreOffice `.registry/*.xcd`
conffiles privately, and writes the resulting runtime identity. Preserve the
package plan and provisioning logs with evidence. It does not resolve/download
arbitrary dependencies or install anything into the server OS.

The current preparation retains 246 package archives (186,961,340 bytes), apt
metadata and the private runtime. T04 plus T05 preparations consume about
1.24 GiB on the server. This measured preparation size is not an aggregate
filesystem quota; keep future preparation within the user's 4 GB budget.

## Capability boundaries

T05 qualifies controlled rendering of authored fixtures and execution-view
isolation. It does not qualify arbitrary formula correctness, general visual
task acceptance, Microsoft Office fidelity or a model/RSI benchmark. Only seven
font files are provisioned; missing fonts can alter real document layout.
General formula/visual checks remain later tasks.

Host COM probing and reopening are unavailable by default. An explicitly
configured trusted COM worker must supply isolation/load/ownership proof and
operate on a disposable verified copy. COM reopening alone never claims
formula recalculation or visual validation. The current environment has no
qualified dedicated Microsoft Office COM worker.
