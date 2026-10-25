"""Small, literal confusion-table controls; no evaluator-derived truth."""
import pytest


def api():
    import importlib.util
    assert importlib.util.find_spec('workagent_rsi.calibration_metrics'), 'T27 calibration implementation missing'
    from workagent_rsi.calibration_metrics import summarize_calibration, calibrate
    return summarize_calibration, calibrate


def test_denominators_gaps_partial_and_incomplete_are_explicit():
    summarize, _ = api()
    rows = [dict(case_id=str(i), truth=t, predicted=p, category=c, source_family='one-family',
                 expected_locations=['A1'], observed_locations=loc, gap_origin=gap)
            for i, (t, p, c, loc, gap) in enumerate([
                ('FAIL','PASS','single_defect',[],None),
                ('FAIL','FAIL','single_defect',['A1'],None),
                ('FAIL','INCOMPLETE','single_defect',[],None),
                ('PASS','FAIL','equivalent',[],None),
                ('PASS','PASS','correct',[],None),
                ('PASS','PARTIAL','correct',[],None),
                ('INCOMPLETE','INCOMPLETE','gap',[],'spec_gap'),
                ('INCOMPLETE','PASS','gap',[],'capability_gap')])]
    report = summarize(rows)
    assert report['false_accept_rate']['numerator'] == 1 and report['false_accept_rate']['denominator'] == 2
    assert report['false_reject_rate']['numerator'] == 2 and report['false_reject_rate']['denominator'] == 3
    assert report['artifact_error_denominator'] == 6 and report['gap_classification']['denominator'] == 2
    assert report['incomplete_artifact_cases'] == 1 and report['partial_policy'] == 'not_accepted'
    assert report['location_accuracy']['numerator'] == 1 and report['location_accuracy']['denominator'] == 1
    assert report['family_count'] == 1 and report['independent_accuracy_claim'] is False
    assert report['false_accept_rate']['interval_95'][0] < .5 < report['false_accept_rate']['interval_95'][1]
    assert summarize([])['false_accept_rate']['value'] is None


def test_duplicate_unknown_and_nonfinite_inputs_fail_closed():
    summarize, _ = api()
    r = dict(case_id='x',truth='PASS',predicted='PASS',category='correct',source_family='f',expected_locations=[],observed_locations=[],gap_origin=None)
    with pytest.raises(ValueError, match='duplicate'):
        summarize([r, r])
    with pytest.raises(ValueError, match='status'):
        summarize([{**r,'predicted':'MAYBE'}])


def test_production_calibration_compiler_does_not_read_labels(tmp_path):
    _, _ = api()
    from workagent_rsi.calibration_metrics import calibration_specs
    from types import SimpleNamespace
    from openpyxl import Workbook
    root = tmp_path / 'small-corpus'
    root.mkdir()
    book = Workbook(); book.active.title='Ledger'
    for row in [('Item','Amount'),('North',12),('South',19),('West',7)]: book.active.append(row)
    book.create_sheet('Notes')['A1']='Keep this source'
    book.save(root/'input.xlsx'); book.close()
    case = SimpleNamespace(domain='excel',case_id='opaque',instruction='Put the full-range SUM formula in Ledger!B6.',
        input_path='input.xlsx',oracle_status='PASS',defect_type=None,category='correct',artifact_valid=True)
    changed = SimpleNamespace(**{**vars(case),'oracle_status':'FAIL','defect_type':'invented','category':'single_defect','artifact_valid':False})
    assert calibration_specs(case, root) == calibration_specs(changed, root)
