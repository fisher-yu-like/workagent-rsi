"""Build a small private runtime from existing SIF core files and hashed wheels.

No package installation on the host, network access, image pulling or root.
The destination must be new. This deliberately excludes application/source/cache
content from the existing SIF. It is a provisioner, never an execution fallback.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--source-offset", type=int, required=True)
parser.add_argument("--seed", type=Path, required=True)
parser.add_argument("--seed-offset", type=int, required=True)
parser.add_argument("--wheelhouse", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    raise SystemExit("output must be a new path")
materials = json.loads((args.wheelhouse / "manifest.json").read_text())
if sum(x["size"] for x in materials) > 33554432:
    raise SystemExit("wheel archive budget exceeded")
for item in materials:
    path = args.wheelhouse / item["filename"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
        raise SystemExit("wheel hash mismatch")
subprocess.run(["unsquashfs", "-no-progress", "-no-xattrs", "-processors", "1", "-offset", str(args.seed_offset),
                "-dest", str(args.output), str(args.seed)], check=True)
libraries = ["ld-linux*", "libc.so*", "libm.so*", "libz.so*", "libexpat.so*", "libssl.so*", "libcrypto.so*",
             "libbz2.so*", "liblzma.so*", "libffi.so*", "libuuid.so*", "libtinfo.so*", "libreadline.so*",
             "libncursesw.so*", "libsqlite3.so*", "libgcc_s.so*", "libstdc++.so*", "libpthread.so*", "libdl.so*",
             "librt.so*", "libutil.so*", "libresolv.so*", "libnsl.so*", "libtirpc.so*"]
selected = ["usr/bin/python3.11", "usr/bin/python3", "usr/lib/python3.11", "usr/lib64", "lib", "lib64"]
selected += ["usr/lib/x86_64-linux-gnu/" + name for name in libraries]
subprocess.run(["unsquashfs", "-no-progress", "-no-xattrs", "-processors", "1", "-f",
                "-offset", str(args.source_offset), "-dest", str(args.output), str(args.source), *selected], check=True)
packages = args.output / "usr/local/lib/python3.11/dist-packages"
packages.mkdir(parents=True, exist_ok=True)
for item in materials:
    with zipfile.ZipFile(args.wheelhouse / item["filename"]) as archive:
        for entry in archive.infolist():
            if entry.filename.startswith("/") or ".." in entry.filename.split("/"):
                raise SystemExit("unsafe wheel path")
        archive.extractall(packages)
for path in (args.output / "task/inputs", args.output / "task/outputs", args.output / "task/scratch"):
    path.mkdir(parents=True, exist_ok=True)
(args.output / "etc/workagent-runtime.json").write_text(json.dumps({
    "source_image_sha256": hashlib.file_digest(args.source.open("rb"), "sha256").hexdigest(),
    "seed_image_sha256": hashlib.file_digest(args.seed.open("rb"), "sha256").hexdigest(),
    "source_offset": args.source_offset, "seed_offset": args.seed_offset, "wheels": materials,
}, indent=2))
print(json.dumps({"runtime": str(args.output), "host_packages_installed": False}))
