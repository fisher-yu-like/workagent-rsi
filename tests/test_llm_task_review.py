import json
from pathlib import Path
import subprocess

from openpyxl import Workbook
import pytest

from workagent_rsi.artifact_assessment import SharedAssessment, spec_from_task
from workagent_rsi.artifact_evaluator import ArtifactEvaluator, outcome_from_score
from workagent_rsi.artifact_verifier import ArtifactVerifier
from workagent_rsi.contracts import TaskSpec, ArtifactRef
from workagent_rsi.harness_artifact_evaluator import HarnessArtifactEvaluator
from workagent_rsi.hashing import sha256_file
from workagent_rsi.model_judgement import ModelReviewConfig, ModelJudgementProvider
from workagent_rsi.task_review import TaskJudgement


def judgement(status="PASS", score=0.37, issues=None):
    return TaskJudgement(
        task_reasonableness="clear",
        task_reason="The request is sufficiently clear.",
        status=status,
        completion=score,
        observed="Authored model response for protocol testing.",
        evidence_ids=["output"],
        issues=issues or [],
    )


class Provider:
    def __init__(self, decision=None):
        self.config = ModelReviewConfig(max_text_chars=600000)
        self.decision = decision or judgement()
        self.calls = []

    def identity_config(self):
        return {"model": "test-double-not-real-judge"}

    def judge(self, request, root):
        self.calls.append(request)
        return self.decision, {"model_calls": 1, "status": "completed"}


def workbook(tmp_path):
    b = Workbook()
    b.active["A1"] = 7
    p = tmp_path / "output.xlsx"
    b.save(p)
    return p


@pytest.mark.parametrize(
    "status,score", [("PASS", 0.37), ("PARTIAL", 0.84), ("FAIL", 0.8)]
)
def test_model_owns_status_and_score_despite_old_coded_constraints(
    tmp_path, status, score
):
    task = TaskSpec(
        task_id="t",
        domain="excel",
        instruction="Use the supplied data.",
        expected_constraints={
            "required_cells": {"Sheet!A1": 999},
            "sales_summary": True,
        },
    )
    provider = Provider(judgement(status, score))
    path = workbook(tmp_path)
    shared = SharedAssessment(provider=provider).inspect(
        spec_from_task(task), {"output": path}
    )
    report = ArtifactEvaluator().evaluate(shared)
    assert report.task_acceptance == status and report.total_score == score * 100
    assert outcome_from_score(report).status == status.lower()
    assert "expected_constraints" not in provider.calls[0]["task"]
    assert report.spec_admission is None and report.requirement_coverage is None


def test_readable_file_without_model_is_not_a_success(tmp_path):
    task = TaskSpec(task_id="t", domain="excel", instruction="Analyze the data.")
    shared = SharedAssessment().inspect(
        spec_from_task(task), {"output": workbook(tmp_path)}
    )
    report = ArtifactEvaluator().evaluate(shared)
    assert report.task_acceptance == "INCOMPLETE" and report.total_score is None


def test_reasonableness_is_a_model_decision_not_review_signature_gate(tmp_path):
    task = TaskSpec(task_id="t", domain="excel", instruction="Fix everything.")
    decision = judgement("NEEDS_REVIEW", None).model_copy(
        update={
            "task_reasonableness": "ambiguous",
            "task_reason": "The intended scope is unspecified.",
        }
    )
    shared = SharedAssessment(provider=Provider(decision)).inspect(
        spec_from_task(task), {"output": workbook(tmp_path)}
    )
    assert shared.judgement == decision
    assert ArtifactEvaluator().evaluate(shared).task_acceptance == "NEEDS_REVIEW"


def test_context_limit_does_not_silently_drop_evidence(tmp_path):
    task = TaskSpec(task_id="t", domain="excel", instruction="Review.")
    provider = Provider()
    provider.config = ModelReviewConfig(max_text_chars=20)
    shared = SharedAssessment(provider=provider).inspect(
        spec_from_task(task), {"output": workbook(tmp_path)}
    )
    assert (
        shared.judgement is None
        and "context budget" in shared.error
        and not provider.calls
    )


def test_changed_input_during_judgement_invalidates_snapshot(tmp_path):
    source = tmp_path / "input.txt"
    source.write_text("Authorized source")
    task = TaskSpec(
        task_id="t", domain="excel", instruction="Review.", input_files=[str(source)]
    )
    provider = Provider()
    original = provider.judge

    def mutate(request, root):
        result = original(request, root)
        source.write_text("Changed")
        return result

    provider.judge = mutate
    with pytest.raises(ValueError, match="changed during"):
        SharedAssessment(provider=provider).inspect(
            spec_from_task(task), {"output": workbook(tmp_path)}
        )


def test_model_issue_and_repair_suggestion_are_not_replaced_by_rule_hints(tmp_path):
    task = TaskSpec(task_id="t", domain="excel", instruction="Review.")
    issue = {
        "description": "Model found a problem.",
        "location": {"artifact": "output", "sheet": "Sheet", "cell": "A1"},
        "kind": "artifact_defect",
        "severity": "major",
        "repair_suggestion": "Model-provided action.",
        "evidence_refs": ["output"],
    }
    shared = SharedAssessment(
        provider=Provider(judgement("PARTIAL", 0.6, [issue]))
    ).inspect(spec_from_task(task), {"output": workbook(tmp_path)})
    result = ArtifactVerifier().verify(shared).issues[0]
    assert (
        result.observed == issue["description"]
        and result.repair_hint == issue["repair_suggestion"]
    )
    assert result.expected is None and result.location.cell == "A1"


@pytest.mark.parametrize("backend", ["api", "codex-cli"])
def test_real_transport_serialization_preserves_task_decision(
    tmp_path, monkeypatch, backend
):
    monkeypatch.setenv("REVIEW_TEST_KEY", "test-secret")
    seen = []
    decision = judgement("PARTIAL", 0.71)

    def transport(url, headers, payload, timeout):
        seen.append(payload)
        return {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": decision.model_dump_json()}
                    ],
                }
            ],
        }

    def runner(command, cwd, timeout, prompt):
        seen.append(prompt)
        Path(command[command.index("--output-last-message") + 1]).write_text(
            decision.model_dump_json(), encoding="utf-8"
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    config = ModelReviewConfig(
        provider=backend, model="test-model", api_key_env="REVIEW_TEST_KEY", retries=0
    )
    provider = ModelJudgementProvider(config, runner=runner, transport=transport)
    result, meta = provider.judge(
        {
            "modality": "task",
            "task": {"instruction": "Review the file."},
            "evidence": {"items": [{"evidence_id": "output", "text": "Facts"}]},
            "images": [],
        },
        tmp_path / "calls",
    )
    assert result == decision and meta["model_calls"] == 1 and len(seen) == 1


def test_harness_uses_same_model_report_and_original_filename(tmp_path):
    path = workbook(tmp_path)
    provider = Provider(judgement("PARTIAL", 0.64))
    task = TaskSpec(task_id="t", domain="excel", instruction="Review the output.")
    ref = ArtifactRef(
        artifact_id="file",
        path=str(path),
        sha256=sha256_file(path),
        media_type="application/octet-stream",
        size_bytes=path.stat().st_size,
    )
    report = HarnessArtifactEvaluator(
        tmp_path / "run", assessment=SharedAssessment(provider=provider)
    ).evaluate(task, [ref], "trace")
    assert (
        report.task_acceptance == "PARTIAL"
        and report.score == 0.64
        and not report.passed
    )
    assert report.score_semantics == "llm-task-review-v1"
    assert Path(provider.calls[0]["evidence"]["items"][0]["file"]).name == "output.xlsx"
    assert (
        json.loads(Path(report.report_paths["score"]).read_text())["task_acceptance"]
        == "PARTIAL"
    )
