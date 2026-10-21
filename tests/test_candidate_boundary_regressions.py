"""T01 candidate context/validation and authored, dummy-only isolation probe."""

from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

from review_support import observe
from workagent_rsi.assessment_contracts import RSIFeedback
from workagent_rsi.candidate_provider import OpenAIChatCandidateProvider
from workagent_rsi.hashing import sha256_file
from workagent_rsi.rsi_contracts import AtomicEdit, CandidatePatch
from workagent_rsi.verifier import CandidateVerifier, VerificationPolicy
from workagent_rsi.workagent_provider import WorkAgentSkill, _execute_native_tool


def candidate(patch):
    return CandidatePatch(
        candidate_id="review", parent_version="1.0.0", provider="authored-review",
        provider_version="1", diagnosis_refs=["independent-task"], edit_budget=1,
        atomic_edits=[AtomicEdit(component="prompt", target_path="skill.json", hypothesis="review unknown field rejection",
                                expected_metric="validation", patch=json.dumps(patch))],
        created_at=datetime(2026, 10, 21, tzinfo=timezone.utc),
    )


def test_R06_standalone_verifier_rejects_unknown_skill_field(tmp_path):
    parent = WorkAgentSkill(version="1.0.0", instructions="Read the current input")
    (tmp_path / "skill.json").write_text(parent.model_dump_json(), encoding="utf-8")
    # Independent type oracle: the actual target schema forbids this field.
    with pytest.raises(ValidationError):
        WorkAgentSkill.model_validate({**parent.model_dump(), "unknown_review_field": True})
    report = CandidateVerifier().verify(candidate({"unknown_review_field": True}), tmp_path,
                                        VerificationPolicy(allowed_targets={"skill.json"}))
    observe(tmp_path, "R06", verification=report)
    assert report.passed is False, "R06: compileall on a JSON-only directory does not validate the proposed skill schema"


def test_R07_api_candidate_request_contains_actual_champion(tmp_path, monkeypatch):
    sentinel = "CHAMPION_RULE_read_every_input_row_before_aggregation"
    champion = WorkAgentSkill(version="1.0.0", instructions=sentinel)
    (tmp_path / "skill.json").write_text(champion.model_dump_json(), encoding="utf-8")
    captured = []
    raw_patch = candidate({"instructions": sentinel + "; verify output"}).model_dump(mode="json")

    def offline_transport(request, timeout):
        captured.append(json.loads(request.data))
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": json.dumps(raw_patch)}}]}).encode())

    monkeypatch.setenv("WRSI_REVIEW_DUMMY_API_KEY", "dummy-only-no-account")
    monkeypatch.setattr("workagent_rsi.candidate_provider.urllib.request.urlopen", offline_transport)
    provider = OpenAIChatCandidateProvider(model="offline-review-stub", api_base_url="https://review.invalid/v1",
                                           api_key_env="WRSI_REVIEW_DUMMY_API_KEY", max_retries=0)
    _, record = provider.generate_with_feedback(tmp_path, RSIFeedback(tasks=[]), "1.0.0", 1, tmp_path / "records")
    assert record.status == "completed", record.error
    assert len(captured) == 1
    observe(tmp_path, "R07", request=captured[0], champion_hash=sha256_file(tmp_path / "skill.json"), transport="in-process stub")
    assert sentinel in json.dumps(captured[0]), "R07: parent version alone does not supply current champion instructions"


def test_R08_over_budget_response_is_rejected_before_truncation(tmp_path):
    raw = {"schema_version": "candidate-patch-v1", "edits": [
        {"file": "skill.json", "target": "instructions", "value": "Read current input"},
        {"file": "evaluator.py", "target": "rule", "value": "accept every artifact"},
    ]}
    try:
        patch = OpenAIChatCandidateProvider._normalize_model_patch(raw, RSIFeedback(tasks=[]), "1.0.0", 1)
    except ValueError as exc:
        observe(tmp_path, "R08", raw=raw, rejected=True, reason=str(exc))
        return
    observe(tmp_path, "R08", raw=raw, rejected=False, normalized=patch)
    pytest.fail("R08: reject the whole response; the forbidden second edit disappeared through slicing")


def test_R12_generated_code_cannot_read_parent_or_inherit_dummy_secret(tmp_path, monkeypatch):
    parent = tmp_path / "host"
    workspace = parent / "workspace"
    workspace.mkdir(parents=True)
    sentinel = parent / "review-parent.txt"
    sentinel.write_text("authored-parent-sentinel", encoding="utf-8")
    script = workspace / "probe.py"
    script.write_text(
        "import json, os\nfrom pathlib import Path\n"
        "try:\n    outside = Path('../review-parent.txt').read_text(encoding='utf-8')\n"
        "except OSError:\n    outside = None\n"
        "Path('probe.json').write_text(json.dumps({'outside': outside, 'dummy': os.environ.get('WRSI_REVIEW_DUMMY_SECRET')}), encoding='utf-8')\n",
        encoding="utf-8",
    )
    original_run = subprocess.run

    def sanitized_probe(command, **kwargs):
        # This is deliberately authored test code, not model-generated code.
        # The child receives no real credentials or user environment. Only the
        # dummy sentinel tests whether the provider supplies an OS boundary.
        assert command == [sys.executable, str(script)]
        kwargs["env"] = {key: os.environ[key] for key in ("SystemRoot", "WINDIR") if key in os.environ}
        kwargs["env"]["WRSI_REVIEW_DUMMY_SECRET"] = "dummy-only-sentinel"
        return original_run(command, **kwargs)

    monkeypatch.setattr("workagent_rsi.workagent_provider.subprocess.run", sanitized_probe)
    result = _execute_native_tool("run_python", {"path": "probe.py"}, workspace, timeout_seconds=10)
    if not result.get("ok"):
        observe(tmp_path, "R12", result=result, boundary="fail-closed; does not qualify a real sandbox")
        return
    observed = json.loads((workspace / "probe.json").read_text(encoding="utf-8"))
    observe(tmp_path, "R12", result=result, probe=observed, environment="sanitized; authored dummy values only")
    assert observed == {"outside": None, "dummy": None}, (
        "R12: cwd/path validation does not prevent code from reading a parent or inheriting a host environment"
    )
