"""Record reproducible local test evidence for the two artifact skills."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--tests", nargs="*", default=[])
    parser.add_argument("--pytest-args", nargs=argparse.REMAINDER, default=[])
    args = parser.parse_args()
    if not args.label.replace("-", "").replace("_", "").isalnum():
        parser.error("label must be a safe directory name")
    root = Path(__file__).resolve().parents[2]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = root / "project_artifacts/results/dual-assessment" / f"{stamp}-{args.label}"
    output.mkdir(parents=True)
    # Keep Windows artifact paths below MAX_PATH; preserve each invocation's temp tree.
    temp = root / ".pytest-tmp" / stamp[-13:-1]
    temp.parent.mkdir(exist_ok=True)
    selected = args.tests
    if args.label.startswith("baseline"):
        selected = subprocess.check_output(["git", "ls-files", "tests/test_*.py"], cwd=root, text=True).splitlines()
    command = [sys.executable, "-m", "pytest", "-q", "--basetemp", str(temp), *selected, *args.pytest_args]
    record = {
        "command": command, "cwd": str(root), "started_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "platform": platform.platform(),
        "dependencies": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "source_hashes": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for folder in ("src", "tests", "skills") for p in (root / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts},
    }
    shim = output / "python-shim"
    shim.mkdir()
    (shim / "py.cmd").write_text(
        '@echo off\r\nif "%1"=="-3.12" shift\r\n"' + sys.executable + '" %*\r\n',
        encoding="utf-8",
    )
    record["python_312_compatibility_shim"] = str((shim / "py.cmd").resolve())
    print(str(output), flush=True)
    (output / "invocation.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    with (output / "stdout.txt").open("w", encoding="utf-8") as stdout, (output / "stderr.txt").open("w", encoding="utf-8") as stderr:
        run = subprocess.run(command, cwd=root, stdout=stdout, stderr=stderr, check=False,
                             env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                                  "PATH": str(shim.resolve()) + os.pathsep + os.environ.get("PATH", "")})
    record.update(exit_code=run.returncode, ended_at=datetime.now(timezone.utc).isoformat())
    (output / "invocation.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print((output / "stdout.txt").read_text(encoding="utf-8", errors="replace")[-6000:])
    return run.returncode


if __name__ == "__main__":
    raise SystemExit(main())
