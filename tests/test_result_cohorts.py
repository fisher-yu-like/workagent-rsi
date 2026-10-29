"""T09 authored evidence fixtures; no actual external data or model claims."""
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

from workagent_rsi.hashing import canonical_json_hash, sha256_file


def module():
    path=Path(__file__).parents[1]/'project_artifacts/phase3_experiments/scripts/analyze_formal.py'
    spec=importlib.util.spec_from_file_location('cohort_test_analyzer',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


def publish(folder,*,mode='pilot',score=0.0,run='run-a',attempt=1,status='completed',arm='base',change=None,admitted=False,evidence_id=None):
    folder.mkdir(parents=True)
    def ref(name,value):
        path=folder/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value,indent=2),encoding='utf-8')
        return {'path':name,'sha256':sha256_file(path)}
    tasks=[{'task_id':'task-1'},{'task_id':'task-2'}]
    if change=='dataset':tasks[0]['input_version']=2
    splits={'develop':canonical_json_hash(tasks)}
    identity={'schema_version':'cohort-identity-v1','mode':mode,'dataset_hash':canonical_json_hash(splits),
        'split_hashes':splits,'evaluator_hash':('b' if change=='evaluator' else 'a')*64,
        'acceptance_hashes':{t['task_id']:('d' if change=='acceptance' else 'c')*64 for t in tasks},
        'model_config':{'provider':'authored-fixture','model':'different' if change=='model' else 'offline'},
        'experiment_arm':arm,'budget_policy':{'max_calls':2 if change=='budget' else 1}}
    identity_ref=ref('identity.json',identity)
    result={'run_id':run,'attempt_id':attempt,'status':status,'identity_hash':canonical_json_hash(identity),
        'evidence_id':evidence_id or canonical_json_hash({'run':run,'attempt':attempt,'mode':mode}),
        'metrics':{'score':score} if status=='completed' else {},
        'task_results':[{'task_id':t['task_id'],'metrics':{'score':score}} for t in tasks] if status=='completed' else []}
    result_ref=ref('result.json',result)
    entry={'run_id':run,'attempt_id':attempt,'experiment_id':'E01','status':status,'metrics':result['metrics'],
           'identity_ref':identity_ref,'result_ref':result_ref}
    if admitted:
        source={'status':'ready','formal_dataset_selected':'authored-test-only','candidates':[{
            'id':'authored-test-only','license_status':'verified','data_license':'TEST FIXTURE ONLY',
            'checksum':'f'*64,'download_status':'admitted'}]}
        source_ref=ref('proof/source.json',source)
        quality_ref=ref('proof/quality.json',{'status':'pass','formal_dataset_selected':'authored-test-only'})
        split=folder/'proof/develop.jsonl';split.write_text('\n'.join(json.dumps(t) for t in tasks)+'\n')
        admission={'schema_version':'cohort-admission-v1','ready':True,'dataset_hash':identity['dataset_hash'],
            'identity_hash':canonical_json_hash(identity),'source_manifest':source_ref,'quality_report':quality_ref,
            'splits':{'develop':{'path':'proof/develop.jsonl','sha256':sha256_file(split)}}}
        entry['admission_ref']=ref('proof/admission.json',admission)
    summary={'mode':mode,'invocation_id':'authored-container','dataset_kind':'external-admitted' if mode=='formal' else 'project-generated',
             'claim_boundary':{'external_benchmark':mode=='formal'},'experiments':[entry]}
    (folder/'summary.json').write_text(json.dumps(summary),encoding='utf-8')
    return summary,identity,result


def rewrite(folder,summary=None,result=None):
    if result is not None:
        (folder/'result.json').write_text(json.dumps(result))
        summary=summary or json.loads((folder/'summary.json').read_text())
        summary['experiments'][0]['result_ref']['sha256']=sha256_file(folder/'result.json')
        summary['experiments'][0]['metrics']=result['metrics']
    (folder/'summary.json').write_text(json.dumps(summary))


def analyze(root):return module().analyze_results(root)
def samples(report):return sum(c['sample_count'] for c in report['cohorts'])


def test_pilot_zero_formal_one_stay_separate_and_global_mean_is_absent(tmp_path):
    publish(tmp_path/'pilot',mode='pilot',score=0,run='pilot')
    publish(tmp_path/'formal',mode='formal',score=1,run='formal',admitted=True)
    result=analyze(tmp_path)
    assert result['numeric_means']=={} and result['claims_allowed'] is False
    means={c['key']['mode']:c['numeric_means']['score'] for c in result['cohorts']}
    assert means=={'pilot':0,'formal':1}


@pytest.mark.parametrize('change',['dataset','evaluator','acceptance','model','budget','arm'])
def test_each_comparability_identity_separates_cohorts(tmp_path,change):
    publish(tmp_path/'one',run='one',score=0)
    publish(tmp_path/'two',run='two',score=1,change=change,arm='other' if change=='arm' else 'base')
    report=analyze(tmp_path)
    assert len(report['cohorts'])==2 and report['numeric_means']=={}


def test_unknown_identity_cannot_authorize_claim_or_enter_numbers(tmp_path):
    folder=tmp_path/'unknown';summary,_,_=publish(folder,mode='formal',score=1)
    del summary['experiments'][0]['identity_ref'];rewrite(folder,summary)
    report=analyze(tmp_path)
    assert not report['claims_allowed'] and report['numeric_means']=={} and samples(report)==0
    assert report['excluded_records']


def test_duplicate_run_attempt_does_not_inflate_count(tmp_path):
    publish(tmp_path/'one',score=1)
    shutil.copytree(tmp_path/'one',tmp_path/'copy')
    report=analyze(tmp_path)
    assert samples(report)==1
    assert report['cohorts'][0]['metric_denominators']['score']==1


def test_conflicting_duplicate_attempt_is_not_arbitrarily_selected(tmp_path):
    publish(tmp_path/'one',score=0)
    publish(tmp_path/'two',score=1)
    report=analyze(tmp_path)
    assert samples(report)==0 and report['excluded_records']


def test_latest_failure_does_not_fall_back_to_older_success(tmp_path):
    publish(tmp_path/'old',score=1,attempt=1)
    publish(tmp_path/'new',attempt=2,status='failed')
    report=analyze(tmp_path)
    assert samples(report)==0 and report['numeric_means']=={}


def test_successful_retry_counts_once_with_latest_attempt_identity(tmp_path):
    publish(tmp_path/'old',attempt=1,status='failed')
    publish(tmp_path/'new',attempt=2,score=1)
    report=analyze(tmp_path)
    assert samples(report)==1 and report['cohorts'][0]['numeric_means']=={'score':1}
    assert report['cohorts'][0]['observations'][0]['attempt_id']==2


def test_invalid_latest_attempt_cannot_resurrect_old_success(tmp_path):
    publish(tmp_path/'old',attempt=1,score=1)
    folder=tmp_path/'new';summary,_,_=publish(folder,attempt=2,score=0)
    del summary['experiments'][0]['identity_ref'];rewrite(folder,summary)
    assert samples(analyze(tmp_path))==0


def test_reused_evidence_across_different_run_ids_is_excluded(tmp_path):
    publish(tmp_path/'one',run='one',evidence_id='e'*64)
    publish(tmp_path/'two',run='two',evidence_id='e'*64)
    assert samples(analyze(tmp_path))==0


@pytest.mark.parametrize('value',[float('nan'),float('inf'),True])
def test_nonfinite_or_boolean_metrics_never_enter_numeric_aggregation(tmp_path,value):
    publish(tmp_path/'bad',score=value)
    report=analyze(tmp_path)
    assert report['numeric_means']=={} and samples(report)==0


def test_completed_task_coverage_must_be_complete_and_not_duplicate(tmp_path):
    folder=tmp_path/'partial';summary,_,result=publish(folder,score=1)
    result['task_results']=result['task_results'][:1];rewrite(folder,summary,result)
    report=analyze(tmp_path)
    assert not report['claims_allowed'] and samples(report)==0


def test_summary_score_must_match_actual_paired_task_observations(tmp_path):
    folder=tmp_path/'bad';summary,_,result=publish(folder,score=1)
    result['task_results'][0]['metrics']['score']=0;rewrite(folder,summary,result)
    assert samples(analyze(tmp_path))==0


def test_hash_tampered_identity_is_excluded(tmp_path):
    folder=tmp_path/'bad';publish(folder,score=1)
    (folder/'identity.json').write_text('{}')
    assert samples(analyze(tmp_path))==0


def test_formal_boolean_alone_never_authorizes_claim(tmp_path):
    publish(tmp_path/'formal',mode='formal',score=1)
    report=analyze(tmp_path)
    assert samples(report)==1 and report['claims_allowed'] is False
    assert report['cohorts'][0]['claims_allowed'] is False


def test_formal_complete_bound_admission_proof_is_cohort_scoped(tmp_path):
    folder=tmp_path/'formal';publish(folder,mode='formal',score=1,admitted=True)
    report=analyze(tmp_path)
    assert report['claims_allowed'] is True and report['cohorts'][0]['claims_allowed'] is True
    assert report['cohorts'][0]['task_observation_count']==2
    (folder/'proof/quality.json').write_text('{"status":"fail"}')
    report=analyze(tmp_path)
    assert report['claims_allowed'] is False


def test_paired_reference_run_is_new_and_preserves_original_history(tmp_path):
    from workagent_rsi import result_cohorts
    original=tmp_path/'historical.json';original.write_text('{"score":0.5}')
    before=original.read_bytes();calls=[]
    def evaluator(task,package):
        calls.append((task['task_id'],package['value']))
        return {'score':package['value']}
    report=result_cohorts.paired_reference_evaluation(tmp_path/'reference_eval_run',
        tasks=[{'task_id':'a'},{'task_id':'b'}],parent_package={'value':0},candidate_package={'value':1},
        evaluator=evaluator,evaluator_hash='a'*64,source_runs={'history.json':original})
    assert len(calls)==4 and report['paired_deltas']=={'score':1}
    assert report['task_count']==2 and original.read_bytes()==before
    assert (tmp_path/'reference_eval_run/reference_eval_run.json').is_file()
    with pytest.raises(FileExistsError):
        result_cohorts.paired_reference_evaluation(tmp_path/'reference_eval_run',tasks=[{'task_id':'a'}],
            parent_package={},candidate_package={},evaluator=evaluator,evaluator_hash='a'*64)


def test_single_verified_cohort_retains_mean_and_traceable_denominators(tmp_path):
    publish(tmp_path/'one',run='one',score=0)
    publish(tmp_path/'two',run='two',score=1)
    result=analyze(tmp_path)
    assert result['numeric_means']=={'score':.5} and samples(result)==2
    assert result['cohorts'][0]['metric_denominators']=={'score':2}
    assert result['cohorts'][0]['task_observation_count']==4
    assert len(result['cohorts'][0]['observations'])==2


def test_retry_cannot_change_the_comparability_identity(tmp_path):
    publish(tmp_path/'old',attempt=1,status='failed')
    publish(tmp_path/'new',attempt=2,score=1,change='model')
    assert samples(analyze(tmp_path))==0


@pytest.mark.parametrize('replacement',[[],None,True])
def test_malformed_formal_admission_is_visible_without_crashing_analysis(tmp_path,replacement):
    folder=tmp_path/'formal';summary,_,_=publish(folder,mode='formal',score=1,admitted=True)
    proof=folder/'proof/admission.json';proof.write_text(json.dumps(replacement))
    summary['experiments'][0]['admission_ref']['sha256']=sha256_file(proof);rewrite(folder,summary)
    report=analyze(tmp_path)
    assert report['claims_allowed'] is False and report['cohorts'][0]['claims_allowed'] is False


def test_evidence_reference_cannot_escape_summary_directory(tmp_path):
    folder=tmp_path/'run';summary,_,_=publish(folder,score=1)
    summary['experiments'][0]['identity_ref']['path']='../run/identity.json';rewrite(folder,summary)
    assert samples(analyze(tmp_path))==0


def test_reference_evaluation_failure_does_not_overwrite_or_invent_results(tmp_path):
    from workagent_rsi.result_cohorts import paired_reference_evaluation
    with pytest.raises(ValueError,match='finite'):
        paired_reference_evaluation(tmp_path/'reference',tasks=[{'task_id':'a'}],parent_package={},candidate_package={},
            evaluator=lambda task,package:{'score':float('nan')},evaluator_hash='a'*64)
    report=json.loads((tmp_path/'reference/reference_eval_run.json').read_text())
    assert report['status']=='failed' and report['rows']==[] and report['claims_allowed'] is False


def test_malformed_claim_boundary_cannot_crash_or_authorize_formal_claim(tmp_path):
    folder=tmp_path/'formal';summary,_,_=publish(folder,mode='formal',admitted=True)
    summary['claim_boundary']=[];rewrite(folder,summary)
    report=analyze(tmp_path)
    assert report['claims_allowed'] is False and report['cohorts'][0]['claims_allowed'] is False


def test_result_attempt_boolean_cannot_impersonate_attempt_one(tmp_path):
    folder=tmp_path/'bad';summary,_,result=publish(folder,score=1)
    result['attempt_id']=True;rewrite(folder,summary,result)
    assert samples(analyze(tmp_path))==0


def test_linked_analysis_subtree_is_visible_exclusion_and_never_authorizes_whole_root(tmp_path):
    from test_evaluation_isolation import link_directory
    root=tmp_path/'analysis'
    publish(root/'formal',mode='formal',admitted=True,run='formal')
    publish(tmp_path/'outside',mode='pilot',run='outside')
    link_directory(root/'linked-inputs',tmp_path/'outside')
    report=analyze(root)
    assert report['claims_allowed'] is False and samples(report)==1
    assert any('linked' in row['reason'] for row in report['excluded_records'])
