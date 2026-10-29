import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from docx import Document
from PIL import Image
import pytest

from workagent_rsi.artifact_assessment import SharedAssessment, spec_from_task
from workagent_rsi.artifact_renderer import RenderedPage, RenderResult
from workagent_rsi.contracts import TaskSpec
from workagent_rsi.hashing import sha256_file
from workagent_rsi.model_judgement import ModelReviewConfig, ModelJudgementProvider
from workagent_rsi.office_observations import read_file
from workagent_rsi.storage import ArtifactStore
from test_llm_task_review import Provider, judgement


@pytest.mark.parametrize("suffix", [".docx", ".xlsx", ".pptx", ".png"])
def test_unreadable_output_is_an_observation_not_a_coded_decision(tmp_path, suffix):
    path = tmp_path / ("output" + suffix)
    path.write_bytes(b"damaged public file")
    provider = Provider(judgement("NEEDS_REVIEW", None))
    task = TaskSpec(task_id="t", domain="word", instruction="Review the output.")
    assessment = SharedAssessment(provider=provider).inspect(
        spec_from_task(task), {"output": path}
    )
    assert assessment.judgement.status == "NEEDS_REVIEW"
    assert assessment.judgement.completion is None
    assert "read_error" in provider.calls[0]["evidence"]["items"][0]
    assert len(provider.calls) == 1


def test_model_can_cite_the_original_task_for_ambiguity(tmp_path, monkeypatch):
    from workagent_rsi.artifact_verifier import ArtifactVerifier

    monkeypatch.setenv("UNIT_REVIEW_KEY", "unit-secret")
    issue = {
        "description": "The requested result is undefined.",
        "location": {"artifact": "task"},
        "kind": "spec_gap",
        "severity": "major",
        "repair_suggestion": "Clarify which result to mark.",
        "evidence_refs": ["task"],
    }
    decision = judgement("NEEDS_REVIEW", None, [issue]).model_copy(
        update={"task_reasonableness": "ambiguous", "evidence_ids": ["task"]}
    )

    def transport(*args):
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

    provider = ModelJudgementProvider(
        ModelReviewConfig(
            provider="api", model="unit-model", api_key_env="UNIT_REVIEW_KEY", retries=0
        ),
        transport=transport,
    )
    output = tmp_path / "output.txt"
    output.write_text("Observed output", encoding="utf-8")
    task = TaskSpec(
        task_id="t", domain="word", instruction="Mark the important result."
    )
    assessment = SharedAssessment(
        provider=provider, output_root=tmp_path / "calls"
    ).inspect(spec_from_task(task), {"output": output})
    report = ArtifactVerifier().verify(assessment)
    assert assessment.judgement == decision
    assert report.issues[0].repair_action.evidence_refs == ["task"]


def test_word_nonbody_parts_and_revision_markup_are_observations(tmp_path):
    path = tmp_path / "output.docx"
    doc = Document()
    doc.add_paragraph("Body")
    doc.save(path)
    with ZipFile(path) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    parts["word/comments.xml"] = (
        f'<w:comments xmlns:w="{ns}"><w:comment w:id="3" w:author="Reviewer"><w:p><w:r><w:t>A real comment</w:t></w:r></w:p></w:comment></w:comments>'.encode()
    )
    parts["word/header1.xml"] = (
        f'<w:hdr xmlns:w="{ns}"><w:p><w:r><w:t>Header text</w:t></w:r></w:p></w:hdr>'.encode()
    )
    with ZipFile(path, "w", ZIP_DEFLATED) as z:
        for name, value in parts.items():
            z.writestr(name, value)
    before = sha256_file(path)
    evidence = read_file(path, "output")
    assert (
        evidence["parts"]["word/comments.xml"]["annotations"][0]["text"]
        == "A real comment"
    )
    assert (
        evidence["parts"]["word/header1.xml"]["paragraphs"][0]["text"] == "Header text"
    )
    assert "status" not in evidence and sha256_file(path) == before


def test_reference_and_output_pages_are_supplied_to_one_task_judgement(tmp_path):
    reference = tmp_path / "reference.png"
    Image.new("RGB", (20, 10), "blue").save(reference)
    doc = Document()
    doc.add_paragraph("Output")
    output = tmp_path / "output.docx"
    doc.save(output)

    class Renderer:
        def identity_config(self):
            return {"renderer": "unit-double"}

        def render(self, path, domain, digest):
            image = tmp_path / "render.png"
            Image.new("RGB", (20, 10), "white").save(image)
            return RenderResult(
                status="available",
                artifact_sha256=digest,
                renderer_identity="unit",
                elapsed_seconds=0,
                pages=[
                    RenderedPage(
                        image_id="page-1",
                        path=str(image),
                        sha256=sha256_file(image),
                        page=1,
                        artifact_location="page/1",
                        width=20,
                        height=10,
                    )
                ],
            )

    provider = Provider()
    task = TaskSpec(
        task_id="t",
        domain="word",
        instruction="Compare the output with the reference.",
        input_files=[str(reference)],
    )
    SharedAssessment(provider=provider, renderer=Renderer()).inspect(
        spec_from_task(task), {"output": output}
    )
    assert len(provider.calls) == 1
    assert {i["image_id"] for i in provider.calls[0]["images"]} == {
        "input-1",
        "output/page-1",
    }


def test_stored_file_keeps_original_filename(tmp_path):
    source = tmp_path / "the-actual-output.docx"
    source.write_bytes(b"file bytes")
    artifact = ArtifactStore(tmp_path / "store").put_file(
        source, "application/octet-stream"
    )
    assert (
        artifact.file_name == source.name
        and Path(artifact.path).name == artifact.sha256
    )


def test_invalid_model_evidence_reference_is_transport_error_not_artifact_failure(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("UNIT_REVIEW_KEY", "unit-secret")
    decision = judgement().model_copy(update={"evidence_ids": ["not-supplied"]})

    def transport(*args):
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

    provider = ModelJudgementProvider(
        ModelReviewConfig(
            provider="api", model="unit-model", api_key_env="UNIT_REVIEW_KEY", retries=0
        ),
        transport=transport,
    )
    result, telemetry = provider.judge(
        {
            "modality": "task",
            "evidence": {"items": [{"evidence_id": "output"}]},
            "images": [],
        },
        tmp_path / "review",
    )
    assert (
        result is None
        and telemetry["status"] == "error"
        and telemetry["model_calls"] == 1
    )
    raw = list((tmp_path / "review").rglob("raw_decision.json"))
    assert json.loads(raw[0].read_text())["status"] == "PASS"


def test_unavailable_key_and_excess_images_never_call_transport(tmp_path, monkeypatch):
    monkeypatch.delenv("UNIT_REVIEW_KEY", raising=False)
    calls = []
    provider = ModelJudgementProvider(
        ModelReviewConfig(
            provider="api", model="unit-model", api_key_env="UNIT_REVIEW_KEY", retries=0
        ),
        transport=lambda *args: calls.append(args),
    )
    result, meta = provider.judge({"modality": "task", "images": []}, tmp_path)
    assert result is None and meta["model_calls"] == 0 and calls == []
