"""Reject missing or unrelated calculation evidence before native scoring."""
from workagent_rsi.benchmark_scoring import score_spreadsheet
from workagent_rsi.hashing import sha256_file


def test_no_stale_formula_cache_score_without_isolated_recalculation(tmp_path):
    task = {'benchmark': 'spreadsheetbench-2', 'category': 'Template', 'split': 'regression'}
    result = score_spreadsheet(task, scorer_path=tmp_path / 'absent.py', scorer_sha256='a' * 64,
                               sources={}, recalculated={}, receipts={})
    assert result['status'] == 'unavailable' and result['score'] is None
    assert result['official_leaderboard_claim'] is False
    files = {}
    for name in ['input', 'reference', 'output']:
        files[name] = tmp_path / (name + '.xlsx')
        files[name].write_bytes(name.encode())
    task['variants'] = [{'inputs': [{'sha256': sha256_file(files['input'])}],
                         'reference': {'sha256': sha256_file(files['reference'])}}]
    receipts = {k: {'status': 'available', 'source_sha256': sha256_file(p),
                   'output_sha256': sha256_file(p), 'qualification': 'unit_fixture'} for k, p in files.items()}
    result = score_spreadsheet(task, scorer_path=tmp_path / 'absent.py', scorer_sha256='a' * 64,
                               sources=files, recalculated=files, receipts=receipts)
    assert result['score'] is None and 'isolated' in result['reason']
    task['variants'][0]['reference']['sha256'] = 'a' * 64
    result = score_spreadsheet(task, scorer_path=tmp_path / 'absent.py', scorer_sha256='a' * 64,
                               sources=files, recalculated=files, receipts=receipts)
    assert result['score'] is None and 'same frozen native variant' in result['reason']


def test_visualization_and_final_cannot_use_development_numeric_scorer(tmp_path):
    for category, split, reason in [('Visualization', 'develop', 'COM'), ('Template', 'final_test', 'one-use')]:
        result = score_spreadsheet({'benchmark': 'spreadsheetbench-2', 'category': category, 'split': split},
            scorer_path=tmp_path / 'not-loaded.py', scorer_sha256='f' * 64,
            sources={}, recalculated={}, receipts={})
        assert result['status'] == 'unavailable' and result['score'] is None
        assert reason in result['reason']
