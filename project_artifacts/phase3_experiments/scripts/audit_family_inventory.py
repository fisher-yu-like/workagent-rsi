"""Audit existing exposed materials; never invent an independent final set."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from workagent_rsi.calibration_data import load_calibration_cases
from workagent_rsi.dataset_splits import TaskFamilyManifest, split_quality_report
from workagent_rsi.environment_manifest import capture_environment
from workagent_rsi.hashing import sha256_file, canonical_json_hash


def audit(calibration_manifest: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(output)
    cases = load_calibration_cases(calibration_manifest)
    pilot_path = ROOT / 'project_artifacts/phase3_experiments/data/raw/tasks_all.jsonl'
    pilot = [json.loads(line) for line in pilot_path.read_text(encoding='utf-8').splitlines()]
    groups = defaultdict(list)
    for case in cases:
        groups[(case.domain, case.input_hash)].append(case)
    families = []
    for (domain, source_hash), group in sorted(groups.items()):
        families.append(TaskFamilyManifest(base_task_id=f'calibration-{domain}-{source_hash[:12]}',
            family_id=group[0].source_family, source_document_id=f'{domain}:{source_hash}',
            source_hash=source_hash, variant_ids=[c.case_id for c in group],
            variant_input_hashes={c.case_id: c.input_hash for c in group}, domain=domain,
            split='develop', exposure='exposed', source_refs=[group[0].source_refs[0]]))
    report = split_quality_report(families)
    pilot_splits = defaultdict(set)
    for task in pilot:
        pilot_splits[task['template_family']].add('promotion_validation' if task['split'] == 'hidden' else task['split'])
    report.update(source_kind='project-generated', calibration_case_count=len(cases),
        calibration_source_family_count=len({c.source_family for c in cases}),
        formal_admitted_base_tasks=0, formal_admitted_instances=0,
        legacy_pilot_task_count=len(pilot), legacy_pilot_family_count=len(pilot_splits),
        legacy_pilot_family_split_overlap={k: sorted(v) for k, v in pilot_splits.items() if len(v) > 1},
        final_content_available=False,
        limitation='Calibration cases are exposed, repeated output controls, not three independent input variants per base. Legacy pilot families already cross splits. Neither is an untouched final set.')
    report['blockers'].append('Independent, unexposed task sources and evaluator-service deployment are not provisioned.')
    report['status'] = 'blocked'
    output.mkdir(parents=True)
    capture_environment(ROOT, output / 'environment.json')
    def write(name, value):
        (output / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    write('family-manifest.json', {'schema_version': 'family-inventory-v1',
        'purpose': 'exposed calibration inventory; not an admitted research taskset',
        'eligible_for_formal_study': False, 'families': [r.model_dump(mode='json') for r in families]})
    write('split-quality-report.json', report)
    write('sealed-final-manifest.json', {'status': 'blocked', 'task_count': 0, 'base_task_count': 0,
        'family_count': 0, 'source_document_count': 0, 'final_test_hash': canonical_json_hash([]),
        'sealed': False, 'reason': 'No unexposed final content; empty-set hash is not a sealed corpus.'})
    write('input-hashes.json', {str(calibration_manifest): sha256_file(calibration_manifest),
        str(pilot_path.relative_to(ROOT)): sha256_file(pilot_path),
        'construction_script': sha256_file(Path(__file__)),
        'protocol': sha256_file(ROOT / 'project_artifacts/phase3_experiments/configs/evaluation_protocol_v2.json')})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibration-manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    started = datetime.now(timezone.utc).isoformat()
    report = audit(args.calibration_manifest, args.output)
    text = json.dumps(report, sort_keys=True)
    (args.output / 'stdout.txt').write_text(text + '\n', encoding='utf-8')
    (args.output / 'stderr.txt').write_text('', encoding='utf-8')
    record = {'command': [sys.executable, str(Path(__file__)), *sys.argv[1:]], 'cwd': str(ROOT),
        'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'started_at': started, 'ended_at': datetime.now(timezone.utc).isoformat(),
        'exit_code': 1, 'audit_completed': True, 'dataset_status': report['status'],
        'files': {p.name: sha256_file(p) for p in args.output.iterdir() if p.is_file()}}
    (args.output / 'run.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(text)
    return 1  # Successful audit found an explicit dataset-scale blocker.


if __name__ == '__main__':
    raise SystemExit(main())
