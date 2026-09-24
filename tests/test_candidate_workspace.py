from pathlib import Path

import pytest

from workagent_rsi.candidate_workspace import CandidateWorkspaceBuilder


def test_candidate_workspace_contains_only_allowlisted_files(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "skill.json").write_text('{"marker_source":"task_id"}', encoding="utf-8")
    (source / "evaluator.py").write_text("SECRET = True", encoding="utf-8")
    (source / "hidden_tasks.jsonl").write_text("hidden", encoding="utf-8")
    destination = tmp_path / "candidate"

    manifest = CandidateWorkspaceBuilder().export(
        source,
        destination,
        allowed_files=["skill.json"],
        context_files={"diagnosis.json": "{}"},
    )

    assert (destination / "skill.json").exists()
    assert (destination / "diagnosis.json").exists()
    assert (destination / "AGENTS.md").exists()
    assert (destination / ".git").is_dir()
    assert not (destination / "evaluator.py").exists()
    assert not (destination / "hidden_tasks.jsonl").exists()
    assert set(manifest.file_hashes) == {"AGENTS.md", "diagnosis.json", "skill.json"}


def test_candidate_workspace_rejects_path_escape(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(ValueError, match="relative"):
        CandidateWorkspaceBuilder().export(source, tmp_path / "candidate", ["../secret"], {})


def test_candidate_workspace_rejects_protected_basename(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "evaluator.py").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="protected"):
        CandidateWorkspaceBuilder().export(source, tmp_path / "candidate", ["evaluator.py"], {})
