from workagent_rsi.external_admission import validate_external_admission, separate_score_channels
from workagent_rsi.hashing import sha256_file


def admitted_fixture(root):
    for name in ('LICENSE','source.zip','native.py','parity.json','input.xlsx','answer.xlsx'):
        (root/name).write_text(name,encoding='utf-8')
    return dict(source_version='pinned-revision',code_license='MIT',data_license_scope='MIT explicit dataset grant',
        provenance=['https://example.test/source/pinned-revision'],
        checksums={p.name:sha256_file(p) for p in root.iterdir()},
        license_evidence=['LICENSE'],native_evaluator_identity='native-v1',
        native_parity={'status':'pass','evaluator_identity':'native-v1','official_environment_match':True,'evidence_ref':'parity.json'},
        boundary={'execution_inputs':['input.xlsx'],'evaluation_only':['answer.xlsx','native.py'],
                  'separate_evaluator_principal':True})


def test_missing_admission_and_reference_overlap_block_formal(tmp_path):
    assert not validate_external_admission({},tmp_path)['formal_ready']
    report=admitted_fixture(tmp_path)
    assert validate_external_admission(report,tmp_path)['formal_ready']
    report['boundary']['execution_inputs'].append('answer.xlsx')
    assert 'reference_or_evaluator_visible_to_agent' in validate_external_admission(report,tmp_path)['blockers']
    report['data_license_scope']=None
    assert 'missing_data_license_scope' in validate_external_admission(report,tmp_path)['blockers']


def test_official_environment_parity_and_hashes_are_required(tmp_path):
    report=admitted_fixture(tmp_path)
    report['native_parity']['official_environment_match']=False
    assert 'native_evaluator_parity_not_qualified' in validate_external_admission(report,tmp_path)['blockers']
    (tmp_path/'native.py').write_text('changed',encoding='utf-8')
    assert 'checksum_mismatch:native.py' in validate_external_admission(report,tmp_path)['blockers']


def test_custom_quality_never_becomes_native_score():
    report=separate_score_channels(custom={'score':.95})
    assert report['native_benchmark'] is None
    assert not report['official_leaderboard_claim']
