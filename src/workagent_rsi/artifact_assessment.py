"""Collect evidence and ask a model to assess the original task."""

import argparse
import json
from pathlib import Path
from zipfile import BadZipFile

from lxml.etree import XMLSyntaxError

from .contracts import TaskSpec
from .hashing import canonical_json_hash, sha256_file
from .office_observations import read_file
from .task_review import TaskAssessment, TaskJudgement, TaskReviewSpec, task_context
from .view_safety import ordinary_file


def assessment_identity(config=None):
    names = (
        "artifact_assessment.py",
        "artifact_evaluator.py",
        "artifact_verifier.py",
        "task_review.py",
        "office_observations.py",
        "model_judgement.py",
        "semantic_assessment.py",
        "review_evidence.py",
        "artifact_renderer.py",
    )
    return canonical_json_hash(
        {
            "protocol": "llm-task-review-v1",
            "files": {
                name: sha256_file(Path(__file__).with_name(name)) for name in names
            },
            "configuration": config or {},
        }
    )


def spec_from_task(task, *, assessment_profile=None):
    task = TaskSpec.model_validate(task)
    return TaskReviewSpec(
        task_id=task.task_id,
        artifacts={"output": task.domain},
        task_context=task_context(task),
        input_hashes={p: sha256_file(ordinary_file(p)) for p in task.input_files},
    )


class SharedAssessment:
    def __init__(self, *, provider=None, renderer=None, output_root=None):
        self.provider, self.renderer = provider, renderer
        self.output_root = Path(output_root or "project_artifacts/results/task-review")

    def identity(self):
        return assessment_identity(
            {
                "provider": self.provider.identity_config()
                if self.provider
                else "disabled",
                "renderer": self.renderer.identity_config()
                if self.renderer
                else "disabled",
            }
        )

    def unavailable(self, spec, reason):
        return TaskAssessment(
            spec=spec,
            spec_hash=spec.fingerprint(),
            evaluator_identity=self.identity(),
            artifact_hashes={key: None for key in spec.artifacts},
            observations=[],
            error=reason,
        )

    def inspect(self, spec, artifacts):
        spec = TaskReviewSpec.model_validate(spec)
        hashes = {
            key: sha256_file(path) if Path(path).is_file() else None
            for key, path in artifacts.items()
        }
        for path, digest in spec.input_hashes.items():
            if sha256_file(ordinary_file(path)) != digest:
                raise ValueError("frozen assessment input changed: " + path)
        if not artifacts or any(value is None for value in hashes.values()):
            return self.unavailable(
                spec, "Output files are unavailable for model review."
            )
        observations = []
        images = []
        files = [(f"input-{i}", p) for i, p in enumerate(spec.input_hashes, 1)] + list(
            artifacts.items()
        )
        for key, value in files:
            path = ordinary_file(value)
            try:
                if path.suffix.lower() == ".png":
                    from PIL import Image

                    with Image.open(path) as im:
                        width, height = im.size
                    images.append(
                        {
                            "image_id": key,
                            "path": str(path),
                            "sha256": sha256_file(path),
                            "artifact_location": key,
                            "width": width,
                            "height": height,
                        }
                    )
                    continue
                observation = read_file(path, key)
            except (ValueError, OSError, BadZipFile, XMLSyntaxError, KeyError) as exc:
                observation = {
                    "artifact": key,
                    "file": str(path),
                    "sha256": sha256_file(path),
                    "read_error": str(exc),
                }
            observations.append({"evidence_id": key, **observation})
            if self.renderer and path.suffix.lower() in {".xlsx", ".docx", ".pptx"}:
                domain = {".xlsx": "excel", ".docx": "word", ".pptx": "powerpoint"}[
                    path.suffix.lower()
                ]
                rendered = self.renderer.render(path, domain, sha256_file(path))
                observations.append(
                    {
                        "evidence_id": key + "-render",
                        "render": rendered.model_dump(mode="json"),
                    }
                )
                images.extend(
                    {
                        **p.model_dump(mode="json"),
                        "image_id": key + "/" + p.image_id,
                        "artifact_location": key + "/" + p.artifact_location,
                    }
                    for p in rendered.pages
                )
        payload = dict(
            spec=spec,
            spec_hash=spec.fingerprint(),
            evaluator_identity=self.identity(),
            artifact_hashes=hashes,
            observations=observations,
        )
        if self.provider is None:
            return TaskAssessment(**payload, error="LLM judge is not configured.")
        request = {
            "modality": "task",
            "task": spec.task_context,
            "evidence": {"items": observations},
            "images": images,
        }
        config = self.provider.config
        if len(json.dumps(request, ensure_ascii=False)) > config.max_text_chars:
            return TaskAssessment(
                **payload,
                error="Evidence exceeds configured context budget; use a larger budget or narrower file-reading operations.",
            )
        decision, telemetry = self.provider.judge(
            request, self.output_root / spec.fingerprint()
        )
        for key, path in files:
            expected = spec.input_hashes.get(str(path), hashes.get(key))
            if expected and sha256_file(ordinary_file(path)) != expected:
                raise ValueError("assessment file changed during model review")
        for image in images:
            if sha256_file(image["path"]) != image["sha256"]:
                raise ValueError("assessment image changed during model review")
        return TaskAssessment(
            **payload,
            judgement=TaskJudgement.model_validate(decision) if decision else None,
            telemetry=telemetry,
            error=telemetry.get("error") if decision is None else None,
        )


def assess(spec, artifacts, *, provider=None, renderer=None):
    from .artifact_evaluator import ArtifactEvaluator
    from .artifact_verifier import ArtifactVerifier

    shared = SharedAssessment(provider=provider, renderer=renderer).inspect(
        spec, artifacts
    )
    return (
        shared,
        ArtifactEvaluator().evaluate(shared),
        ArtifactVerifier().verify(shared),
    )


def save_reports(output, shared, score, issues):
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    for name, value in (("assessment", shared), ("score", score), ("issues", issues)):
        with (root / (name + ".json")).open("x", encoding="utf-8") as f:
            f.write(value.model_dump_json(indent=2))
    (root / "report.md").write_text(
        f"# Task review: {score.task_id}\n\nModel decision: {score.task_acceptance}\n\nQuality: {score.quality_score}\n\n"
        + (
            shared.judgement.observed
            if shared.judgement
            else shared.error or "No model judgement."
        ),
        encoding="utf-8",
    )


def main(argv=None, *, entry="both"):
    parser = argparse.ArgumentParser(
        description="Review original task and Office artifacts with an LLM"
    )
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-config", type=Path)
    args = parser.parse_args(argv)
    request = json.loads(args.request.read_text(encoding="utf-8-sig"))
    task = TaskSpec.model_validate(request["task"])
    task = task.model_copy(
        update={
            "input_files": tuple(
                str((args.request.resolve().parent / p).resolve())
                for p in task.input_files
            )
        }
    )
    artifacts = {
        k: str((args.request.resolve().parent / p).resolve())
        for k, p in request["artifacts"].items()
    }
    from .model_judgement import configured_assessment
    from .artifact_evaluator import ArtifactEvaluator
    from .artifact_verifier import ArtifactVerifier

    config = (
        json.loads(args.model_config.read_text(encoding="utf-8-sig"))
        if args.model_config
        else {}
    )
    shared = configured_assessment(config, args.output / "model-evidence").inspect(
        spec_from_task(task), artifacts
    )
    score = ArtifactEvaluator().evaluate(shared)
    issues = ArtifactVerifier().verify(shared)
    save_reports(args.output, shared, score, issues)
    print((issues if entry == "verifier" else score).model_dump_json(indent=2))
    return 0
