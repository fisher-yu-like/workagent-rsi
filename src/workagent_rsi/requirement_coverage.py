"""Task-bound, reviewed requirement coverage, independent of candidate artifacts."""
from __future__ import annotations

from pathlib import Path

from .assessment_contracts import (AcceptanceSpec, RequirementCoverage, RequirementInventory,
                                   SpecAdmissionReport, TaskRequirement)
from .contracts import TaskSpec
from .hashing import canonical_json_hash, sha256_file
from .view_safety import ordinary_file


def task_context(task):
    task = TaskSpec.model_validate(task)
    return {name:getattr(task, name) for name in ['task_id','domain','instruction','input_files']}


def task_fingerprint(task):
    context = task_context(task)
    context['input_hashes'] = {str(p):sha256_file(ordinary_file(p)) for p in context['input_files']}
    return canonical_json_hash(context)


def spec_coverage_fingerprint(spec):
    payload = spec.model_dump(mode='json')
    # Review binds all check/expected/weight/input semantics, without recursively
    # hashing the receipt that contains that binding. Profiles use the same spec.
    for key in ['evaluation_profile','task_context','requirement_inventory']:
        payload.pop(key, None)
    return canonical_json_hash(payload)


def _source_quote(task, requirement, spec):
    if requirement.source_ref == 'task.instruction':
        return requirement.source_quote in task.instruction
    # Only explicitly authorized, frozen text inputs may ground a quote.
    if requirement.source_ref.startswith('input:'):
        index = int(requirement.source_ref.split(':',1)[1])
        if index < 0 or index >= len(task.input_files):
            return False
        path = ordinary_file(task.input_files[index])
        digest = spec.input_hashes.get(str(path)) or spec.input_hashes.get(task.input_files[index])
        if digest != sha256_file(path) or path.stat().st_size > 1048576:
            return False
        text = path.read_text(encoding='utf-8')
        return requirement.source_quote in text and sha256_file(path) == digest
    return False


def validate_spec_coverage(task, inventory, spec, *, evaluation_profile):
    if evaluation_profile not in {'structural_only','task_acceptance','research',None}:
        raise ValueError('unknown evaluation profile')
    spec = AcceptanceSpec.model_validate(spec.model_dump(mode='json'))
    reasons, uncovered, mappings = [], [], {}
    task_hash = None
    binding = spec_coverage_fingerprint(spec)
    if evaluation_profile is None:
        return SpecAdmissionReport(status='LEGACY_UNREVIEWED', requirement_coverage=RequirementCoverage(
            mandatory=0,covered=0,ratio=0), reasons=['Legacy declared checks have no reviewed task-coverage admission.'],
            spec_binding_hash=binding)
    if evaluation_profile == 'structural_only':
        return SpecAdmissionReport(status='NOT_ASSESSED',evaluation_profile=evaluation_profile,
            requirement_coverage=RequirementCoverage(mandatory=0,covered=0,ratio=0),
            reasons=['Structural/declared-check observations do not assess whole-task acceptance.'],spec_binding_hash=binding)
    mandatory, covered = 0, 0
    try:
        task = TaskSpec.model_validate(task)
        task_hash = task_fingerprint(task)
        if task.task_id != spec.task_id:
            raise ValueError('task/spec identity mismatch')
        inv = RequirementInventory.model_validate(inventory)
        if inv.task_id != task.task_id:
            reasons.append('inventory/task identity mismatch')
        proof = inv.provenance
        if (not inv.reviewed or proof.get('kind') not in {'human_review','reviewed_benchmark'}
                or not isinstance(proof.get('reviewer'),str) or not proof['reviewer'].strip()
                or not isinstance(proof.get('review_ref'),str) or not proof['review_ref'].strip()):
            reasons.append('independent review provenance is missing; model self-review is insufficient')
        if proof.get('task_hash') != task_hash:
            reasons.append('review does not bind the current task and authorized inputs')
        if proof.get('spec_hash') != binding:
            reasons.append('review does not bind the frozen acceptance checks')
        ids = [r.requirement_id for r in inv.requirements]
        if len(ids) != len(set(ids)):
            reasons.append('duplicate task requirement identity')
        checks = {r.requirement_id:r for r in spec.requirements}
        for requirement in inv.requirements:
            if requirement.mandatory:
                mandatory += 1
            mappings[requirement.requirement_id] = requirement.check_ids
            valid = True
            if not _source_quote(task, requirement, spec):
                reasons.append(requirement.requirement_id+': quote is not grounded in an authorized source')
                valid = False
            if (requirement.validation_method == 'uncovered' or not requirement.check_ids
                    or len(set(requirement.check_ids)) != len(requirement.check_ids)
                    or any(name not in checks or not checks[name].applicable for name in requirement.check_ids)):
                valid = False
                if requirement.mandatory:
                    reasons.append(requirement.requirement_id+': mandatory obligation lacks applicable check coverage')
            if any(name in checks and (
                    (requirement.validation_method in {'semantic','visual','human'} and checks[name].check != requirement.validation_method)
                    or (requirement.validation_method == 'deterministic' and checks[name].check in {'semantic','visual','human'}))
                    for name in requirement.check_ids):
                valid = False
                reasons.append(requirement.requirement_id+': validation method does not match the mapped checks')
            if requirement.mandatory:
                if valid:
                    covered += 1
                else:
                    uncovered.append(requirement.requirement_id)
        if not mandatory:
            reasons.append('no independently reviewed mandatory requirements')
    except (ValueError, TypeError, OSError, IndexError, UnicodeError) as exc:
        reasons.append('invalid task/inventory: '+str(exc))
    return SpecAdmissionReport(status='SPEC_INCOMPLETE' if reasons else 'PASS',
        evaluation_profile=evaluation_profile, requirement_coverage=RequirementCoverage(
            mandatory=mandatory,covered=covered,ratio=covered/mandatory if mandatory else 0),
        uncovered_requirement_ids=uncovered,reasons=reasons,mappings=mappings,
        task_hash=task_hash,spec_binding_hash=binding)


def admission_for_spec(spec):
    return validate_spec_coverage(spec.task_context, spec.requirement_inventory, spec,
                                  evaluation_profile=spec.evaluation_profile)
