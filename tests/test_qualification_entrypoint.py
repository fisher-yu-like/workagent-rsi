import json
from pathlib import Path
import urllib.request

import pytest

from workagent_rsi.study_entrypoint import main, qualification_report
from workagent_rsi.study_protocol import prepare_experiment, StudyConfig, freeze_manifest
from workagent_rsi.hashing import sha256_file


def test_dry_run_never_reads_credentials_or_opens_network(monkeypatch,tmp_path,capsys):
    monkeypatch.setattr(urllib.request,'urlopen',lambda *a,**k:pytest.fail('network in dry-run'))
    config=tmp_path/'config.json'
    config.write_text(json.dumps({'model':'test','endpoint':'https://example.test/v1'}),encoding='utf-8')
    assert main('qualification',['--config',str(config),'--dry-run'])==0
    report=json.loads(capsys.readouterr().out)
    assert report['dry_run_paid_calls']==0 and not report['live_ready']
    assert 'missing_capability_receipt' in report['blockers']
    assert not report['research_qualified']
    assert main('qualification',['--config',str(config)])==2


def test_frozen_manifest_cannot_be_reconfigured_on_resume(tmp_path):
    config=StudyConfig(model='test',endpoint='https://example.test/v1')
    first=prepare_experiment(config)
    freeze_manifest(first,tmp_path/'study')
    freeze_manifest(first,tmp_path/'study',resume=True)
    changed=prepare_experiment(config.model_copy(update={'model':'another'}))
    with pytest.raises(ValueError,match='identity changed'):
        freeze_manifest(changed,tmp_path/'study',resume=True)
    assert qualification_report(tmp_path)['three_domain_repair_complete'] is False


def test_repair_report_requires_saved_artifacts_and_success(tmp_path):
    for domain,ext in [('excel','xlsx'),('word','docx'),('powerpoint','pptx')]:
        root=tmp_path/domain;root.mkdir()
        for name in ('attempt-000','attempt-001'):(root/name).mkdir()
        (root/'attempt-000'/'code-manifest.json').write_text(json.dumps({'sources':[{'name':'agent.py','text':'saved code'}]}),encoding='utf-8')
        (root/'attempt-001'/'request.json').write_text(json.dumps({'task':{'domain':domain}}),encoding='utf-8')
        artifact=root/('answer.'+ext);artifact.write_bytes(b'fixture artifact bytes')
        (root/'attempt-manifest.json').write_text(json.dumps({'selected_attempt':1,'attempts':[
            {'state':'FAILED'}, {'state':'SUCCEEDED','artifacts':[{'path':str(artifact),'sha256':sha256_file(artifact)}]}]}),encoding='utf-8')
    report=qualification_report(tmp_path)
    assert report['three_domain_repair_complete']
    assert report['research_qualified'] is False
