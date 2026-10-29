import json
from pathlib import Path
import shutil
import subprocess

import pytest

from test_benchmark_blind_pack import load_script
from test_standard_judge_pilot import pack_fixture
from workagent_rsi.hashing import sha256_file
from workagent_rsi.human_calibration import intake_human_submission


@pytest.mark.parametrize('cohort',['standards-12','natural-blind'])
def test_followup_has_empty_choices_and_exports_only_nonblind_adjudication(tmp_path,cohort):
    module=load_script('prepare_targeted_adjudication.py');pack=tmp_path/'pack';pack_fixture(pack)
    public=pack/'blind-review-pack';manifest=json.loads((public/'review-manifest.json').read_text(encoding='utf-8'))
    manifest['case_ids']=[r['case_id'] for r in manifest['cases']]
    for row in manifest['cases']:row['cohort']=cohort
    (public/'review-manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    intake=tmp_path/'intake';intake.mkdir();(intake/'external-submission.json').write_text('authored human-intake fixture',encoding='utf-8')
    (intake/'submission-receipt.json').write_text(json.dumps({'rubric_hash':'a'*64,'submission_hash':sha256_file(intake/'external-submission.json')}),encoding='utf-8')
    (intake/'human-labels.jsonl').write_text('\n'.join(json.dumps({'case_id':f'case-{i}','label':'PASS'}) for i in range(6)),encoding='utf-8')
    notes=tmp_path/'notes.json';notes.write_text(json.dumps([{'case_id':f'case-{i}','focus':'Check source <and> output.'} for i in range(6)]),encoding='utf-8')
    result=module.prepare(pack,intake,notes,tmp_path/'followup',cohort=cohort)
    page=Path(result['page']).read_text(encoding='utf-8')
    assert result['labels_generated']==0 and page.count('<option value="">')==6
    assert page.count('<h3>原任务说明</h3>')==6 and ' selected' not in page
    assert 'Check source &lt;and&gt; output.' in page
    if cohort=='natural-blind':
        assert '6 份自然成品逐项复核' in page
        assert '不要因为外观大致正常就选择 PASS' in page
    node=shutil.which('node');assert node,'Node is required for the offline form behavior check'
    data=json.loads((tmp_path/'followup/adjudication-request.json').read_text(encoding='utf-8'))
    # Inject data as named constants rather than replacing identifiers in expressions.
    harness="const DATA="+json.dumps(data)+";const SCRIPT="+json.dumps(module.SCRIPT)+";"+r'''
const vm=require('vm');const elements={};let saved=null,alerts=0;
elements['review-data']={textContent:JSON.stringify(DATA)};elements.export={};elements.reviewer={value:'fixture-reviewer'};
for(const cid of DATA.case_ids){elements['label-'+cid]={value:''};elements['note-'+cid]={value:''};elements['checked-'+cid]={checked:false};}
vm.runInNewContext(SCRIPT,{document:{getElementById:id=>elements[id],createElement:()=>({click(){}})},alert:()=>alerts++,Blob,URL:{createObjectURL:blob=>{saved=blob;return 'fixture';},revokeObjectURL:()=>{}}});
elements.export.onclick();if(saved||alerts!==1)throw Error('empty export accepted');
for(const cid of DATA.case_ids){elements['label-'+cid].value='INCOMPLETE';elements['note-'+cid].value='Unable to verify source';elements['checked-'+cid].checked=true;}
elements.export.onclick();saved.text().then(t=>process.stdout.write(t));
'''
    done=subprocess.run([node,'-e',harness],capture_output=True,text=True,check=True)
    payload=json.loads(done.stdout)
    assert payload['source_kind']=='human_adjudication' and not payload['independent_blind_review']
    assert len(payload['labels'])==6
    submitted=tmp_path/'adjudication.json';submitted.write_text(done.stdout,encoding='utf-8')
    with pytest.raises(ValueError,match='unknown submission source'):
        intake_human_submission(submitted,tmp_path/'not-blind',reviewer_id='fixture-reviewer',evidence_ref='authored test',review_manifest=manifest)
