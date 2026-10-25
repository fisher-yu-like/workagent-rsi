"""Qualify native scoring on a real input control, without agent/model calls.

An unmodified task input is a control observation, never a natural model output.
It need not fail every task. This verifies integration, not scoring accuracy.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from workagent_rsi.apptainer_sandbox import ApptainerPolicy, ApptainerSSHExecutor
from workagent_rsi.benchmark_scoring import score_spreadsheet
from workagent_rsi.hashing import sha256_file
from workagent_rsi.spreadsheet_recalc import RecalculationEngine


def qualify(task_path, scorers_path, cache, policy_path, output):
    if output.exists():
        raise FileExistsError(output)
    data = json.loads(task_path.read_text(encoding='utf-8'))
    task = data['task']
    if task['split'] != 'develop':
        raise ValueError('native integration controls must come from development families')
    variant = task['variants'][0]
    root = Path(data['root'])
    source, gold = root / variant['inputs'][0]['path'], root / variant['reference']['path']
    if sha256_file(source) != variant['inputs'][0]['sha256'] or sha256_file(gold) != variant['reference']['sha256']:
        raise ValueError('control source identity changed')
    policy = ApptainerPolicy.model_validate_json(policy_path.read_text(encoding='utf-8'))
    engine = RecalculationEngine(sandbox=ApptainerSSHExecutor(policy), qualification='isolated_run',
                                 timeout_seconds=90, output_root=output / 'worker-evidence')
    output.mkdir(parents=True)
    receipts = {}
    for name, path in [('input', source), ('reference', gold)]:
        result = engine.recalculate(path, output / (name + '.xlsx'))
        receipts[name] = result.model_dump(mode='json')
        (output / 'recalculation.json').write_text(json.dumps(receipts, indent=2, default=str) + '\n', encoding='utf-8')
    if all(r['status'] == 'available' for r in receipts.values()):
        scorer = json.loads(scorers_path.read_text(encoding='utf-8'))['scorers'][task['benchmark']]
        report = score_spreadsheet(task, scorer_path=cache / scorer['local_path'], scorer_sha256=scorer['sha256'],
            sources={'input': source, 'reference': gold, 'output': source},
            recalculated={'input': output / 'input.xlsx', 'reference': output / 'reference.xlsx', 'output': output / 'input.xlsx'},
            receipts={**receipts, 'output': receipts['input']})
    else:
        report = {'status': 'unavailable', 'score': None, 'reason': 'isolated recalculation unavailable'}
    report.update({'qualification_scope': 'real benchmark input-control integration, not model performance or accuracy calibration',
        'control': 'unmodified input versus native reference', 'model_calls': 0, 'natural_model_outputs': 0,
        'completed_at': datetime.now(timezone.utc).isoformat(), 'task_file_sha256': sha256_file(task_path),
        'source_sha256': sha256_file(source), 'reference_sha256': sha256_file(gold),
        'recalculation_receipts': {k: {f: v for f, v in r.items() if f != 'values'} for k, r in receipts.items()}})
    (output / 'report.json').write_text(json.dumps(report, indent=2, default=str) + '\n', encoding='utf-8')
    return {k: v for k, v in report.items() if k not in ('recalculation_receipts', 'recalculation')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', type=Path, required=True)
    parser.add_argument('--scorers', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--sandbox-policy', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(qualify(args.task, args.scorers, args.cache, args.sandbox_policy, args.output), ensure_ascii=False))
