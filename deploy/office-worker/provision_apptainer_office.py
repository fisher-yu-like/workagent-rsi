"""Prepare a private Office runtime from signed-index Debian package records.

Never installs packages into the host, runs maintainer scripts, changes an
account, or modifies the base runtime. All dependencies remain in a new rootfs.
Run only as an explicit provisioning step, never as an execution fallback.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request

from apptainer_worker import fingerprint

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--package-plan', type=Path, required=True)
parser.add_argument('--base-runtime', type=Path, required=True)
parser.add_argument('--base-sha256', required=True)
parser.add_argument('--destination', type=Path, required=True)
args = parser.parse_args()
packages = json.loads(args.package_plan.read_text())
if args.destination.exists() or args.destination.is_symlink():
    raise SystemExit('destination must be a new directory')
total = sum(p['size'] for p in packages)
installed = sum(p['installed_kib'] for p in packages)*1024
if total > 268435456 or installed > 1288490188:
    raise SystemExit('private runtime package budget exceeded')
if shutil.disk_usage(args.destination.parent).free < total+installed+268435456:
    raise SystemExit('insufficient free staging space')
if fingerprint(args.base_runtime)[0] != args.base_sha256:
    raise SystemExit('base runtime identity changed')
archive = args.package_plan.parent/'archives'
archive.mkdir(exist_ok=True)


def download(package):
    name = package['filename']
    if Path(name).name != name or not name.endswith('.deb') or not package['url'].startswith('https://'):
        raise ValueError('invalid Debian package reference')
    destination = archive/name
    if not destination.exists():
        digest = hashlib.sha256()
        size = 0
        with urllib.request.urlopen(package['url'],timeout=30) as response, destination.open('xb') as stream:
            while chunk := response.read(1048576):
                size += len(chunk)
                if size > package['size']: raise ValueError('package size overflow')
                digest.update(chunk)
                stream.write(chunk)
        if size != package['size'] or digest.hexdigest()!=package['sha256']:
            raise ValueError('package checksum/size mismatch')
    with destination.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=package['sha256']:
            raise ValueError('cached package checksum mismatch')
    return destination


with ThreadPoolExecutor(max_workers=4) as pool:
    paths = list(pool.map(download,packages))
print(json.dumps({'downloaded_bytes':total,'packages':len(paths)}),flush=True)
# cp -a preserves hardlink groups WITHIN the new tree, never across the base.
subprocess.run(['cp','-a',str(args.base_runtime),str(args.destination)],check=True)
for path in paths:
    subprocess.run(['dpkg-deb','--extract',str(path),str(args.destination)],check=True,
                   stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL)
# Debian normally copies these conffiles through ucf in postinst. Materialize
# only the shipped registry bytes inside our private tree; never run postinst.
registry_files = {}
registry_source = args.destination/'usr/lib/libreoffice/share/.registry'
for source in sorted(registry_source.rglob('*.xcd')):
    relative = source.relative_to(registry_source)
    target = args.destination/'etc/libreoffice/registry'/relative
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target)
    registry_files[relative.as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
if fingerprint(args.base_runtime)[0] != args.base_sha256:
    raise SystemExit('base runtime was modified')
record = {'base_runtime_sha256':args.base_sha256,'packages':packages,
          'maintainer_scripts_executed':False,'host_packages_installed':False,
          'materialized_registry_files':registry_files}
(args.destination/'etc/workagent-office-runtime.json').write_text(json.dumps(record,indent=2))
identity,files,logical_bytes = fingerprint(args.destination)
record.update(runtime_sha256=identity,files=files,logical_bytes=logical_bytes)
(args.destination.parent/'office-runtime-identity.json').write_text(json.dumps(record,indent=2))
print(json.dumps({'runtime':str(args.destination),'sha256':identity,'files':files,'logical_bytes':logical_bytes}),flush=True)
