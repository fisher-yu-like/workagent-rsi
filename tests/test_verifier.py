import subprocess
from datetime import datetime, timezone
from pathlib import Path

from workagent_rsi.verifier import CandidateVerifier, VerificationPolicy
from workagent_rsi.rsi_contracts import AtomicEdit, CandidatePatch


def candidate(target="skill.json", patch='{"marker_source":"required_text"}') -> CandidatePatch:
    return CandidatePatch(
        candidate_id="c1",
        parent_version="0.1.0",
        provider="test",
        provider_version="1",
        diagnosis_refs=["a" * 64],
        atomic_edits=[AtomicEdit(component="prompt", target_path=target, hypothesis="improve marker", expected_metric="success", patch=patch)],
        edit_budget=1,
        created_at=datetime.now(timezone.utc),
    )


def test_verifier_stops_before_commands_on_critical_violation(tmp_path: Path):
    calls = []

    def runner(command, cwd, timeout):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    report = CandidateVerifier(runner=runner).verify(
        candidate(target="evaluator.py"),
        tmp_path,
        VerificationPolicy(allowed_targets={"skill.json"}, protected_paths={"evaluator.py"}),
    )
    assert report.passed is False
    assert calls == []
    assert "path_policy" in report.executed_checks


def test_verifier_accepts_schema_valid_skill_patch(tmp_path: Path):
    (tmp_path / "skill.json").write_text('{"marker_source":"task_id"}', encoding="utf-8")

    def runner(command, cwd, timeout):
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = CandidateVerifier(runner=runner).verify(
        candidate(),
        tmp_path,
        VerificationPolicy(allowed_targets={"skill.json"}),
    )
    assert report.passed is True
    assert report.critical_violations == []
    assert "compile" in report.executed_checks
    assert report.evidence_refs


def test_verifier_rejects_invalid_json_patch(tmp_path: Path):
    report = CandidateVerifier().verify(
        candidate(patch="not-json"),
        tmp_path,
        VerificationPolicy(allowed_targets={"skill.json"}),
    )
    assert report.passed is False
    assert any("JSON" in item for item in report.critical_violations)
