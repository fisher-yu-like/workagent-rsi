"""Evaluator-side bridge to pinned native spreadsheet scorers.

Only hash-qualified upstream Python is loaded. Recalculated copies and their
source bindings are mandatory: empty or stale formula caches cannot qualify a
spreadsheet. Scores cover the native cells only, never whole-artifact quality.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from .hashing import sha256_file
from .spreadsheet_recalc import RecalcResult
from .view_safety import ordinary_file


def score_spreadsheet(task: dict, *, scorer_path: Path, scorer_sha256: str,
                      sources: dict[str, Path], recalculated: dict[str, Path],
                      receipts: dict[str, dict]) -> dict:
    def gap(reason):
        return {'status': 'unavailable', 'score': None, 'reason': reason,
                'whole_task_admission': 'NOT_ASSESSED', 'official_leaderboard_claim': False}
    if task['benchmark'] not in ('spreadsheetbench-2', 'spreadsheetbench-v1'):
        return gap('workspace tasks require separate rubric judging')
    if task.get('category') == 'Visualization':
        return gap('native visualization requires Windows Excel/WPS COM and its approved VLM')
    if task.get('split') == 'final_test':
        return gap('final evaluation must use the separate one-use evaluator')
    keys = {'input', 'reference', 'output'}
    if set(sources) != keys or set(recalculated) != keys or set(receipts) != keys:
        return gap('input/reference/output recalculation evidence missing')
    original_input = sha256_file(ordinary_file(sources['input']))
    original_reference = sha256_file(ordinary_file(sources['reference']))
    variant = next((v for v in task['variants'] if len(v['inputs']) == 1
                    and v['inputs'][0]['sha256'] == original_input
                    and v.get('reference', {}).get('sha256') == original_reference), None)
    if variant is None:
        return gap('input/reference do not belong to the same frozen native variant')
    records = {}
    for name in sorted(keys):
        result = RecalcResult.model_validate(receipts[name])
        if result.status != 'available' or result.qualification != 'isolated_run':
            return gap('isolated recalculation unavailable for ' + name)
        source = ordinary_file(sources[name])
        produced = ordinary_file(recalculated[name])
        if (sha256_file(source) != result.source_sha256 or sha256_file(produced) != result.output_sha256
                or not result.environment.get('office_binary_sha256') or not result.evidence_refs):
            return gap('recalculation source/output/engine binding mismatch for ' + name)
        records[name] = result.model_dump(mode='json')
    if len({r['engine_identity'] for r in records.values()}) != 1:
        return gap('all three workbooks require the same recalculation configuration')
    scorer_path = ordinary_file(scorer_path)
    if len(scorer_sha256) != 64 or sha256_file(scorer_path) != scorer_sha256:
        raise ValueError('native scorer content changed')
    spec = importlib.util.spec_from_file_location('pinned_spreadsheet_scorer_' + scorer_sha256, scorer_path)
    if spec is None or spec.loader is None:
        raise ValueError('native scorer is not a loadable Python module')
    scorer = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(scorer)
    except ImportError as exc:
        return gap('native scorer dependency unavailable: ' + str(exc))
    meta = task['private_evaluation']
    try:
        if task['benchmark'] == 'spreadsheetbench-2':
            source_name = variant['inputs'][0]['path']
            raw = scorer.compare_workbooks_with_regression(str(recalculated['input']), str(recalculated['reference']),
                str(recalculated['output']), meta['answer_position'],
                with_font_color='Color' in source_name, with_formula='Embedded' in source_name)
        else:
            raw = scorer.compare_workbooks(str(recalculated['reference']), str(recalculated['output']),
                meta['instruction_type'], meta['answer_position'])
    except Exception as exc:
        return gap('native scorer error: ' + type(exc).__name__ + ': ' + str(exc))
    return {'status': 'pass' if raw[0] else 'fail', 'score': 1.0 if raw[0] else 0.0,
            'native_result': list(raw), 'scorer_sha256': scorer_sha256,
            'recalculation': records, 'whole_task_admission': 'NOT_ASSESSED',
            'official_leaderboard_claim': False,
            'scope': 'Pinned native target-cell check with recorded isolated recalculation; not whole-artifact quality.'}
