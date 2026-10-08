"""Adapt the shared Office assessment chain to the Harness evaluator contract."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Sequence

from .artifact_assessment import SharedAssessment, save_reports, spec_from_task
from .artifact_evaluator import ArtifactEvaluator
from .artifact_verifier import ArtifactVerifier
from .assessment_contracts import AcceptanceSpec, Assessment, ScoreReport
from .contracts import ArtifactRef, EvaluationReport, TaskSpec
from .hashing import canonical_json_hash, sha256_file
from .office_checks import EXPECTED_SUFFIXES


class HarnessArtifactEvaluator:
    """Run one evidence-bound assessment and adapt its reports for Harness."""

    def __init__(
        self,
        run_root: str | Path,
        *,
        model_review_config=None,
        assessment: SharedAssessment | None = None,
    ) -> None:
        self.run_root = Path(run_root)
        self.run_root.mkdir(parents=True, exist_ok=True)
        if assessment is None:
            from .model_judgement import configured_assessment

            assessment = configured_assessment(
                model_review_config or {}, self.run_root / "model_evidence"
            )
        self.assessment = assessment

    def evaluate(
        self, task: TaskSpec, artifacts: Sequence[ArtifactRef], trace_id: str
    ) -> EvaluationReport:
        spec = spec_from_task(task)
        mapping, mapping_error = self._resolve_mapping(spec, artifacts)
        shared = None
        if mapping_error is None:
            with tempfile.TemporaryDirectory(
                prefix="assessment-input-", dir=self.run_root
            ) as temporary:
                paths: dict[str, Path] = {}
                for index, (key, ref) in enumerate(mapping.items(), start=1):
                    source = Path(ref.path)
                    if not source.is_file() or sha256_file(source) != ref.sha256:
                        mapping_error = (
                            f"stored artifact {ref.artifact_id} is missing or its SHA-256 changed"
                        )
                        break
                    target = Path(temporary) / f"artifact-{index}{EXPECTED_SUFFIXES[spec.artifacts[key]]}"
                    shutil.copyfile(source, target)
                    if sha256_file(target) != ref.sha256 or sha256_file(source) != ref.sha256:
                        mapping_error = (
                            f"stored artifact {ref.artifact_id} changed while preparing assessment"
                        )
                        break
                    paths[key] = target
                if mapping_error is None:
                    shared = self.assessment.inspect(spec, paths)

        if mapping_error is not None:
            shared = self._incomplete_assessment(spec, mapping_error)
        assert shared is not None

        score = ArtifactEvaluator().evaluate(shared)
        issues = ArtifactVerifier().verify(shared)
        report_root = self.run_root / "assessment"
        save_reports(report_root, shared, score, issues)

        requirements = {item.requirement_id: item for item in spec.requirements}
        critical_failures = []
        for check in score.criterion_results:
            requirement = requirements[check.requirement_id]
            if requirement.critical and check.status not in {"PASS", "NOT_APPLICABLE"}:
                location = check.location.model_dump(exclude_none=True)
                critical_failures.append(
                    f"{check.requirement_id}: status={check.status}; actual={check.observed!r}; "
                    f"expected={check.expected!r}; location={location}"
                )
        warnings = [
            f"{issue.requirement_id}: {issue.repair_hint}"
            for issue in issues.issues
            if issue.severity in {"minor", "advisory"}
        ]
        dimensions = {
            name: None if value is None else round(value / 100, 6)
            for name, value in score.dimension_scores.items()
        }
        channel_status = self._channel_status(shared, score)
        report_paths = {
            name: str((report_root / filename).resolve())
            for name, filename in {
                "assessment": "assessment.json",
                "score": "score.json",
                "issues": "issues.json",
                "human_readable": "report.md",
            }.items()
        }
        evidence = [
            *(f"artifact:{name}:{digest}" for name, digest in score.artifact_hashes.items()),
            *(f"assessment_evidence:{item}" for item in score.evidence_refs),
            f"trace:{trace_id}",
            f"assessment_report:{report_paths['assessment']}",
            f"score_report:{report_paths['score']}",
            f"issue_report:{report_paths['issues']}",
        ]
        return EvaluationReport(
            passed=score.acceptance_status == "PASS",
            score=None if score.total_score is None else score.total_score / 100,
            critical_failures=critical_failures,
            warnings=warnings,
            dimensions=dimensions,
            evidence=evidence,
            channel_status=channel_status,
            assessment_identity=score.evaluator_identity,
            report_paths=report_paths,
        )

    @staticmethod
    def _resolve_mapping(
        spec: AcceptanceSpec, artifacts: Sequence[ArtifactRef]
    ) -> tuple[dict[str, ArtifactRef], str | None]:
        if not artifacts:
            return {}, "no generated Office artifacts are available for assessment"
        if len(spec.artifacts) == 1 and len(artifacts) == 1:
            return {next(iter(spec.artifacts)): artifacts[0]}, None

        expected = set(spec.artifacts)
        named: dict[str, ArtifactRef] = {}
        errors: list[str] = []
        for ref in artifacts:
            if not ref.name:
                errors.append(f"artifact {ref.artifact_id} has no declared output name")
            elif ref.name in named:
                errors.append(f"duplicate generated artifact name: {ref.name}")
            else:
                named[ref.name] = ref
        missing = sorted(expected - set(named))
        unexpected = sorted(set(named) - expected)
        if missing:
            errors.append("acceptance spec has no exact output mapping for: " + ", ".join(missing))
        if unexpected:
            errors.append("generated outputs are not declared by the acceptance spec: " + ", ".join(unexpected))
        if errors:
            return {}, "; ".join(errors)
        return {key: named[key] for key in spec.artifacts}, None

    def _incomplete_assessment(self, spec: AcceptanceSpec, reason: str) -> Assessment:
        """Bind mapping failures to every applicable criterion as an assessment gap."""

        shared = self.assessment.inspect(spec, {})
        payload = shared.model_dump(mode="json")
        evidence_by_id = {item["evidence_id"]: item for item in payload["evidence"]}
        checks = []
        evidence = []
        for check in payload["checks"]:
            if check["status"] == "NOT_APPLICABLE":
                checks.append(check)
                evidence.extend(
                    evidence_by_id[reference]
                    for reference in check["evidence_refs"]
                )
                continue
            observed = {"reason": "artifact mapping incomplete", "detail": reason}
            evidence_id = canonical_json_hash(
                {
                    "spec": spec.fingerprint(),
                    "requirement": check["requirement_id"],
                    "hashes": payload["artifact_hashes"],
                    "status": "UNAVAILABLE",
                    "observed": observed,
                }
            )
            original = evidence_by_id[check["evidence_refs"][0]]
            evidence.append(
                {
                    **original,
                    "evidence_id": evidence_id,
                    "observed": observed,
                    "artifact_sha256": None,
                    "artifact_hashes": payload["artifact_hashes"],
                }
            )
            checks.append(
                {
                    **check,
                    "status": "UNAVAILABLE",
                    "completion": None,
                    "observed": observed,
                    "evidence_refs": [evidence_id],
                    "message": reason,
                }
            )
        payload["checks"] = checks
        payload["evidence"] = evidence
        payload["telemetry"] = {
            **payload.get("telemetry", {}),
            "mapping": {"status": "incomplete", "error": reason},
        }
        return Assessment.model_validate(payload)

    @staticmethod
    def _channel_status(shared: Assessment, score: ScoreReport) -> dict[str, str]:
        requirements = {item.requirement_id: item for item in shared.spec.requirements}
        grouped: dict[str, list[str]] = {}
        for check in shared.checks:
            requirement = requirements[check.requirement_id]
            channel = requirement.check if requirement.check in {"semantic", "visual"} else "deterministic"
            grouped.setdefault(channel, []).append(check.status)

        result = {
            "assessment": (
                "incomplete"
                if score.acceptance_status == "INCOMPLETE" or score.total_score is None
                else "completed"
            ),
            "evaluator": shared.evaluator_identity,
            "verifier": shared.evaluator_identity,
        }
        for channel, statuses in grouped.items():
            if any(status in {"UNAVAILABLE", "ERROR", "NEEDS_REVIEW"} for status in statuses):
                result[channel] = "incomplete"
            elif any(status == "FAIL" for status in statuses):
                result[channel] = "failed"
            else:
                result[channel] = "completed"
        return result
