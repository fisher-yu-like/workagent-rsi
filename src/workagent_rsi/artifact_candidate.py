"""Offline bounded policy used to qualify feedback plumbing, not a trained model."""

import json
from datetime import datetime, timezone
from pathlib import Path

from .candidate_provider import _workspace_hash
from .hashing import canonical_json_hash, sha256_file
from .rsi_contracts import AtomicEdit, CandidatePatch, ProviderRecord


class ArtifactFeedbackProvider:
    provider_version = "artifact-feedback-policy-v1"

    def generate_with_feedback(self, workspace, feedback, parent_version, edit_budget, record_root):
        started = datetime.now(timezone.utc)
        current = json.loads((Path(workspace) / "skill.json").read_text(encoding="utf-8"))
        desired = {}
        refs = []
        if feedback.mode == "structured":
            for row in feedback.tasks:
                for issue in row.get("issues", []):
                    hint = issue.get("skill_improvement_hint") or ""
                    refs.extend(issue["evidence_refs"])
                    for key, value in (("sales_rows", "all"), ("sales_chart", True), ("sales_number_format", True)):
                        if f"{key}={str(value).lower()}" in hint and current.get(key) != value:
                            desired[key] = value
        elif feedback.mode == "brief":
            # The brief arm uses only requirement classes; it has no detailed hints.
            for row in feedback.tasks:
                for message in row.get("errors", []):
                    if message.startswith("chart:"):
                        desired["sales_chart"] = True
                    if message.startswith("format."):
                        desired["sales_number_format"] = True
        else:
            # A score-only bounded search tries the next unenabled execution option.
            for key, value in (("sales_chart", True), ("sales_number_format", True), ("sales_rows", "all")):
                if current.get(key) != value:
                    desired[key] = value
                    break
        if not desired:
            # A legal no-op is evaluated and rejected for lack of measured improvement.
            desired["sales_chart"] = current.get("sales_chart", True)
        edits = [AtomicEdit(component="tool_policy", target_path="skill.json",
            hypothesis=f"Apply {key}={value} based on {feedback.mode} develop feedback and recheck artifacts",
            expected_metric="artifact-v1.quality_score", patch=json.dumps({key: value})) for key, value in list(desired.items())[:edit_budget]]
        fingerprint = canonical_json_hash(feedback.model_dump(mode="json"))
        candidate = CandidatePatch(candidate_id=canonical_json_hash({"parent": parent_version, "feedback": fingerprint, "edits": [e.model_dump() for e in edits]})[:20],
            parent_version=parent_version, provider="artifact-feedback-policy", provider_version=self.provider_version,
            diagnosis_refs=refs or [fingerprint], atomic_edits=edits, edit_budget=edit_budget, created_at=started)
        root = Path(record_root)
        root.mkdir(parents=True, exist_ok=True)
        path = root / "candidate.json"
        path.write_text(candidate.model_dump_json(indent=2), encoding="utf-8")
        record = ProviderRecord(provider="artifact-feedback-policy", provider_version=self.provider_version, command=[],
            prompt_hash=fingerprint, workspace_hash=_workspace_hash(Path(workspace)), started_at=started, ended_at=datetime.now(timezone.utc),
            exit_code=0, status="completed", output_ref=sha256_file(path))
        (root / "provider_record.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")
        return candidate, record
