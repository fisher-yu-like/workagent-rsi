"""Use the same task-level LLM review in Harness and skill evaluation."""

import shutil
import tempfile
from pathlib import Path

from .artifact_assessment import save_reports, spec_from_task
from .artifact_evaluator import ArtifactEvaluator, outcome_from_score
from .artifact_verifier import ArtifactVerifier
from .contracts import EvaluationReport
from .hashing import sha256_file
from .office_checks import EXPECTED_SUFFIXES


class HarnessArtifactEvaluator:
    def __init__(
        self,
        run_root,
        *,
        model_review_config=None,
        assessment=None,
        assessment_profile=None,
    ):
        self.run_root = Path(run_root)
        self.run_root.mkdir(parents=True, exist_ok=True)
        if assessment is None:
            from .model_judgement import configured_assessment

            assessment = configured_assessment(
                model_review_config or {}, self.run_root / "model_evidence"
            )
        self.assessment = assessment

    def evaluate(self, task, artifacts, trace_id):
        spec = spec_from_task(task)
        with tempfile.TemporaryDirectory(
            prefix="assessment-input-", dir=self.run_root
        ) as temporary:
            paths = {}
            error = None
            for index, ref in enumerate(artifacts, 1):
                source = Path(ref.path)
                if not source.is_file() or sha256_file(source) != ref.sha256:
                    error = "Stored artifact missing or changed: " + ref.artifact_id
                    break
                key = "output" if len(artifacts) == 1 else f"output-{index}"
                filename = (
                    Path(ref.file_name).name
                    if ref.file_name
                    else source.name
                    if source.suffix
                    else "artifact" + EXPECTED_SUFFIXES.get(task.domain, ".txt")
                )
                target = Path(temporary) / str(index) / filename
                target.parent.mkdir()
                shutil.copyfile(source, target)
                if sha256_file(target) != ref.sha256:
                    error = "Artifact changed during copying"
                    break
                paths[key] = target
            shared = (
                self.assessment.unavailable(spec, error)
                if error
                else self.assessment.inspect(spec, paths)
            )
        score = ArtifactEvaluator().evaluate(shared)
        outcome = outcome_from_score(score)
        issues = ArtifactVerifier().verify(shared)
        report_root = self.run_root / "assessment"
        save_reports(report_root, shared, score, issues)
        report_paths = {
            name: str((report_root / file).resolve())
            for name, file in {
                "assessment": "assessment.json",
                "score": "score.json",
                "issues": "issues.json",
                "human_readable": "report.md",
            }.items()
        }
        return EvaluationReport(
            passed=score.task_acceptance == "PASS",
            score=outcome.quality_score,
            task_acceptance=score.task_acceptance,
            quality_score=outcome.quality_score,
            score_semantics=score.score_semantics,
            assessment_outcome=outcome,
            critical_failures=[
                i.observed
                for i in issues.issues
                if i.kind == "artifact_defect" and i.severity in {"blocking", "major"}
            ],
            warnings=[shared.error] if shared.error else [],
            dimensions={},
            evidence=[f"trace:{trace_id}", *score.evidence_refs],
            report_paths=report_paths,
            channel_status={
                "assessment": "completed" if shared.judgement else "incomplete",
                "judge": "llm",
            },
            assessment_identity=shared.evaluator_identity,
        )
