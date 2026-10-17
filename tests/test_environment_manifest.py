"""T00: environment capture records capabilities without exporting secrets."""

import json
import subprocess
import sys
from pathlib import Path

from workagent_rsi.environment_manifest import capture_environment


def test_capture_environment_records_commit_and_dirty_paths_without_secrets(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "tracked.txt").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-q", "-m", "baseline"],
        cwd=repo,
        check=True,
    )
    (repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
    secret = "secret-value-must-never-be-exported"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    output = tmp_path / "environment.json"

    manifest = capture_environment(repo, output)

    assert manifest["git_commit"] == subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    assert sys.version_info >= (3, 11)
    assert manifest["python_executable"] == sys.executable
    assert "tracked.txt" in manifest["dirty_paths"]
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "changed\n"
    assert json.loads(output.read_text(encoding="utf-8")) == manifest
    assert secret not in output.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY" not in output.read_text(encoding="utf-8")
    assert manifest["capabilities"]["office_com"]["status"] == "not_probed"
    assert manifest["capabilities"]["api"]["live_connection"] == "not_probed"


def test_capture_environment_never_overwrites_existing_output(tmp_path: Path):
    output = tmp_path / "environment.json"
    output.write_text("original", encoding="utf-8")
    try:
        capture_environment(tmp_path, output)
    except FileExistsError:
        pass
    else:
        raise AssertionError("environment capture must not overwrite evidence")
    assert output.read_text(encoding="utf-8") == "original"
