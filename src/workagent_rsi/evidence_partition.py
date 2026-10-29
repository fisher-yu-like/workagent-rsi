"""Bounded evidence partitions, trusted inline sources and review provenance."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import Field, model_validator

from .assessment_contracts import AssessmentModel
from .hashing import canonical_json_hash


class AuthorizedSource(AssessmentModel):
    source_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    sha256: str
    reference: str = Field(min_length=1)

    @model_validator(mode='after')
    def content_identity(self):
        if hashlib.sha256(self.text.encode('utf-8')).hexdigest() != self.sha256:
            raise ValueError('authorized inline source hash mismatch')
        return self


class EvidenceBudget(AssessmentModel):
    max_chars: int = Field(default=60000, ge=1, strict=True)
    max_items: int = Field(default=2000, ge=1, strict=True)
    max_partitions: int = Field(default=64, ge=1, le=64, strict=True)


class EvidenceChunk(AssessmentModel):
    partition_id: str
    items: list[dict[str, Any]]


class EvidencePartition(AssessmentModel):
    partitions: list[EvidenceChunk]
    required_evidence_ids: list[str]
    excluded_items: list[dict[str, str]]
    uncovered: list[dict[str, str]]

    @property
    def complete(self):
        covered = [item['evidence_id'] for part in self.partitions for item in part.items]
        return bool(self.required_evidence_ids) and not self.uncovered and set(covered) == set(self.required_evidence_ids)


def _in_scope(item, location):
    observed = item['location']
    for name, value in location.model_dump(exclude_none=True).items():
        if name == 'region':
            # Free-text regions are not a supported semantic selector.
            return False
        if name == 'cell' and ':' in value:
            from openpyxl.utils.cell import range_boundaries
            if 'cell' not in observed:
                return False
            a,b,c,d = range_boundaries(value)
            x,y,_,_ = range_boundaries(observed['cell'])
            if not a <= x <= c or not b <= y <= d:
                return False
        elif observed.get(name) != value:
            return False
    return True


def partition_evidence(items, requirement, budget) -> EvidencePartition:
    budget = EvidenceBudget.model_validate(budget)
    identities = [item['evidence_id'] for item in items]
    if len(set(identities)) != len(identities) or any(not isinstance(i,str) or not i for i in identities):
        raise ValueError('evidence identities must be nonempty and unique')
    required, excluded, uncovered, chunks, current = [], [], [], [], []

    def size(rows):
        return len(json.dumps(rows,ensure_ascii=False))

    def flush():
        if current:
            chunks.append(EvidenceChunk(partition_id='p-'+canonical_json_hash(current)[:20],items=list(current)))
            current.clear()

    for item in items:
        eid = item['evidence_id']
        if not _in_scope(item, requirement.location):
            excluded.append({'evidence_id':eid,'reason':'outside declared requirement location'})
            continue
        required.append(eid)
        if size([item]) > budget.max_chars:
            uncovered.append({'evidence_id':eid,'reason':'single evidence item exceeds character budget'})
            continue
        if current and (len(current) >= budget.max_items or size(current+[item]) > budget.max_chars):
            flush()
        if len(chunks) >= budget.max_partitions:
            uncovered.append({'evidence_id':eid,'reason':'partition count budget exhausted'})
            continue
        current.append(item)
    flush()
    return EvidencePartition(partitions=chunks,required_evidence_ids=required,excluded_items=excluded,uncovered=uncovered)


class ReviewRecord(AssessmentModel):
    review_id: str
    decision: dict[str, Any]
    evidence_refs: list[str]


class JudgeResult(AssessmentModel):
    decision: dict[str, Any] | None
    reviews: list[ReviewRecord]
    model_identity: dict[str, Any]
    actual_model_calls: int = Field(ge=0)
    disagreement: bool
    confidence_basis: Literal['uncalibrated_self_report'] = 'uncalibrated_self_report'

    @model_validator(mode='after')
    def distinct_reviews(self):
        if len({r.review_id for r in self.reviews}) != len(self.reviews):
            raise ValueError('review identities must be unique')
        return self


def cached_review_telemetry(telemetry):
    """Retain historical decisions without claiming a new independent review."""
    result = {**telemetry,'model_calls':0,'independent_reviews':0,'cache_hit':True}
    if 'judge_result' in result:
        result['reused_judge_result'] = result.pop('judge_result')
    return result


def validate_consistency_groups(groups, required_pages, *, required, max_images):
    """Explicit joint-image comparisons; require a connected coverage graph."""
    if type(required) is not bool or not isinstance(groups,list) or len(groups)>64:
        raise ValueError('invalid cross-partition consistency policy')
    seen, adjacency = set(), {p:set() for p in required_pages}
    for group in groups:
        if (not isinstance(group,list) or len(group)<2 or len(group)>max_images
                or any(type(p) is not int or p not in adjacency for p in group) or len(set(group))!=len(group)):
            raise ValueError('consistency groups require 2..batch-budget distinct required pages')
        seen.update(group)
        for page in group:
            adjacency[page].update(group)
    if required:
        if seen!=set(required_pages):
            raise ValueError('cross-partition consistency groups do not cover every required page')
        reached, pending = set(), [required_pages[0]]
        while pending:
            page=pending.pop()
            if page not in reached:
                reached.add(page);pending.extend(adjacency[page]-reached)
        if reached!=set(required_pages):
            raise ValueError('cross-partition consistency groups must connect the required pages')
    return groups
