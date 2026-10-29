"""Versioned external admission and separate native/custom score channels."""
from pathlib import Path
import re

from pydantic import BaseModel, ConfigDict, Field

from .hashing import sha256_file
from .view_safety import ordinary_file, relative_reference


class ExternalAdmissionReport(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source_version: str | None=None
    code_license: str | None=None
    data_license_scope: str | None=None
    provenance: list[str]=Field(default_factory=list)
    checksums: dict[str,str]=Field(default_factory=dict)
    native_evaluator_identity: str | None=None
    boundary: dict=Field(default_factory=dict)
    native_parity: dict=Field(default_factory=dict)
    license_evidence: list[str]=Field(default_factory=list)


def validate_external_admission(report, root):
    report=ExternalAdmissionReport.model_validate(report)
    root=Path(root).resolve();blockers=[]
    for name in ('source_version','code_license','data_license_scope','native_evaluator_identity'):
        if not getattr(report,name):blockers.append('missing_'+name)
    if not report.provenance or any(not p.startswith('https://') for p in report.provenance):
        blockers.append('missing_primary_source_provenance')
    if not report.checksums: blockers.append('missing_checksums')
    for reference,digest in report.checksums.items():
        try:
            path=ordinary_file(root/relative_reference(reference))
            if not re.fullmatch('[0-9a-f]{64}',digest) or sha256_file(path)!=digest:
                blockers.append('checksum_mismatch:'+reference)
        except (OSError,ValueError):blockers.append('unavailable_source:'+reference)
    if not report.license_evidence or any(ref not in report.checksums for ref in report.license_evidence):
        blockers.append('missing_hash_bound_data_permission')
    inputs=report.boundary.get('execution_inputs',[])
    private=report.boundary.get('evaluation_only',[])
    if not inputs or not private or not report.boundary.get('separate_evaluator_principal'):
        blockers.append('unqualified_executor_evaluator_boundary')
    try:
        input_paths=[root/relative_reference(p) for p in inputs]
        private_paths=[root/relative_reference(p) for p in private]
        if any(a==b or a in b.parents or b in a.parents for a in input_paths for b in private_paths):
            blockers.append('reference_or_evaluator_visible_to_agent')
        if any(not p.exists() for p in input_paths+private_paths):blockers.append('boundary_path_missing')
    except ValueError:blockers.append('invalid_boundary_path')
    parity=report.native_parity
    if not (parity.get('status')=='pass' and parity.get('evaluator_identity')==report.native_evaluator_identity
            and parity.get('official_environment_match') is True and parity.get('evidence_ref') in report.checksums):
        blockers.append('native_evaluator_parity_not_qualified')
    return {'schema_version':'external-admission-v2','formal_ready':not blockers,
            'blockers':sorted(set(blockers)),'admission':report.model_dump(mode='json'),
            'official_leaderboard_claim':False}


def separate_score_channels(*, native=None, custom=None):
    if native is not None and not native.get('scorer_sha256'):
        raise ValueError('native score requires pinned official evaluator identity')
    return {'native_benchmark':native,'custom_artifact_quality':custom,
            'official_leaderboard_claim':False,
            'scope':'Native target/rubric scope and custom declared artifact checks remain separate.'}
