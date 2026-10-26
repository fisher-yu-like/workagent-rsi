"""Candidate-visible context, derived only from verified skills and develop data."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .assessment_contracts import RSIFeedback
from .hashing import canonical_json_hash, sha256_file
from .rsi_contracts import FailureDiagnosis
from .run_contracts import RunContract
from .rsi_feedback import candidate_feedback,candidate_diagnoses
from .view_safety import ordinary_file


PUBLIC_LESSON = 'Verify every declared requirement against the saved artifact before returning it.'


class LessonRecord(RunContract):
    """Only evaluator-authored general rules can enter candidate memory."""
    source_split: Literal['develop'] = 'develop'
    evidence_refs: list[str] = Field(min_length=1)
    generalized_rule: Literal[PUBLIC_LESSON] = PUBLIC_LESSON
    failure_class: Literal['artifact_verification'] = 'artifact_verification'
    applicability: list[Literal['excel', 'word', 'powerpoint']] = Field(
        default_factory=lambda: ['excel', 'word', 'powerpoint'])
    excluded_values: list[str] = Field(default_factory=list, max_length=0)


class PublicLesson(RunContract):
    source_split: Literal['develop'] = 'develop'
    source_feedback_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    statement: Literal[PUBLIC_LESSON] = PUBLIC_LESSON
    record: LessonRecord | None = None


class CandidateContext(RunContract):
    schema_version: Literal['candidate-context-v1'] = 'candidate-context-v1'
    parent_version: str = Field(min_length=1)
    champion_package: dict
    champion_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    champion_file_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    champion_hash_source: Literal['registry', 'export']
    develop_feedback: RSIFeedback
    public_lessons: list[PublicLesson] = Field(default_factory=list)
    diagnoses: list[FailureDiagnosis] = Field(default_factory=list)
    edit_budget: int = Field(ge=1)
    max_context_bytes: int = Field(default=131072, ge=256, le=1048576)

    @model_validator(mode='after')
    def identity_and_budget(self):
        if canonical_json_hash(self.champion_package) != self.champion_hash:
            raise ValueError('champion package hash mismatch')
        if self.champion_package.get('version', self.parent_version) != self.parent_version:
            raise ValueError('champion package version differs from parent version')
        safe = candidate_feedback(self.develop_feedback)
        if safe.model_dump(mode='json') != self.develop_feedback.model_dump(mode='json'):
            raise ValueError('candidate feedback contains unapproved data')
        if [d.model_dump(mode='json') for d in candidate_diagnoses(self.diagnoses)] != [d.model_dump(mode='json') for d in self.diagnoses]:
            raise ValueError('candidate diagnoses contain private evidence')
        size = len(json.dumps(self.model_dump(mode='json'), ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8'))
        if size > self.max_context_bytes:
            raise ValueError(f'candidate context budget exceeded: {size} bytes > {self.max_context_bytes}; no content truncated')
        return self

    def fingerprint(self):
        return canonical_json_hash(self.model_dump(mode='json'))


def build_candidate_context(workspace, parent_version, edit_budget, *, feedback=None,
                            expected_champion_hash=None, diagnoses=(), public_feedback_history=(),
                            max_context_bytes=131072) -> CandidateContext:
    source = ordinary_file(Path(workspace) / 'skill.json')
    digest = sha256_file(source)
    package = json.loads(source.read_text(encoding='utf-8'))
    if not isinstance(package, dict):
        raise ValueError('champion skill.json must contain an object')
    content_hash = canonical_json_hash(package)
    if expected_champion_hash is not None and expected_champion_hash != content_hash:
        raise ValueError('exported champion hash differs from registry package hash')
    safe = candidate_feedback(feedback if feedback is not None else RSIFeedback(tasks=[]))
    lessons = []
    seen = set()
    for prior in public_feedback_history:
        prior = candidate_feedback(prior)
        if any(row.get('issues') or row.get('errors') or row.get('acceptance_status') == 'FAIL' for row in prior.tasks):
            fingerprint = canonical_json_hash(prior.model_dump(mode='json'))
            if fingerprint not in seen:
                seen.add(fingerprint)
                lessons.append(PublicLesson(source_feedback_hash=fingerprint,
                    record=LessonRecord(evidence_refs=[fingerprint])))
    if sha256_file(source) != digest:
        raise ValueError('champion changed during context preparation')
    return CandidateContext(parent_version=parent_version, champion_package=package, champion_hash=content_hash,
                            champion_file_sha256=digest, champion_hash_source='registry' if expected_champion_hash else 'export',
                            develop_feedback=safe, public_lessons=lessons, diagnoses=candidate_diagnoses(diagnoses),
                            edit_budget=edit_budget, max_context_bytes=max_context_bytes)


def validate_candidate_context(context, workspace):
    # Frozen models can still have mutable nested containers. Revalidate them.
    context = CandidateContext.model_validate(context.model_dump())
    source = ordinary_file(Path(workspace) / 'skill.json')
    if (sha256_file(source) != context.champion_file_sha256
            or canonical_json_hash(json.loads(source.read_text(encoding='utf-8'))) != context.champion_hash):
        raise ValueError('champion changed after candidate context export')
    return context


def persist_candidate_context(context, record_root, prompt):
    root = Path(record_root)
    root.mkdir(parents=True, exist_ok=True)
    record = {'context_hash': context.fingerprint(), 'context': context.model_dump(mode='json')}
    (root / 'context.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # No auth headers, environment variables, protected split reports or private
    # registry/evaluation references are serialized into this request evidence.
    (root / 'request-redacted.json').write_text(json.dumps({'prompt': prompt, 'context_hash': context.fingerprint()},
                                                            ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
