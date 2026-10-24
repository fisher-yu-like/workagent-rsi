import subprocess
import sys
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
    assert report.compile_status == 'not_applicable'
    assert report.behavior_status == 'not_run' and report.quality_verified is False
    assert report.evidence_refs


def test_json_verifier_does_not_execute_candidate_authored_tests_on_host(tmp_path: Path):
    (tmp_path / "skill.json").write_text('{"marker_source":"task_id"}', encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_candidate.py").write_text("def test_candidate(): pass\n", encoding="utf-8")
    commands = []

    def runner(command, cwd, timeout):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    report = CandidateVerifier(runner=runner).verify(
        candidate(), tmp_path, VerificationPolicy(allowed_targets={"skill.json"})
    )

    assert report.passed is True
    assert commands == []
    assert report.compile_status == 'not_applicable'
    assert report.test_results['candidate_authored_tests'] == 'not_run'


def test_verifier_rejects_invalid_json_patch(tmp_path: Path):
    report = CandidateVerifier().verify(
        candidate(patch="not-json"),
        tmp_path,
        VerificationPolicy(allowed_targets={"skill.json"}),
    )
    assert report.passed is False
    assert any("JSON" in item for item in report.critical_violations)
