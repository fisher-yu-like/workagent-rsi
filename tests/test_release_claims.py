import json
import shutil

from openpyxl import Workbook

from workagent_rsi.artifact_assessment import SharedAssessment
from workagent_rsi.evidence_bundle import write_evidence_bundle
from workagent_rsi.hashing import sha256_file
from workagent_rsi.release_validation import validate_release, replay_assessment_bundle, ENGINEERING_CHECKS


def test_missing_human_or_external_evidence_never_becomes_research_pass(tmp_path):
    checks={}
    source=tmp_path/'source.py';source.write_text('x=1\n',encoding='utf-8')
    for name in ENGINEERING_CHECKS:
        payload={'exit_code':0}
        if name=='full_pytest':payload.update(cases=[{'status':'passed'}],source_hashes={'source.py':sha256_file(source)})
        if name=='calibration_90':payload.update(case_count=90,known_critical_false_accepts=0,permitted_equivalent_false_rejects=0)
        if name=='moved_bundle_replay':payload.update(fresh_assessment=True,identity_preserved=True)
        if name=='credential_scan':payload['findings']=[]
        if name=='linux_non_com':payload.update(platform='linux',actual_execution=True)
        path=tmp_path/(name+'.json');path.write_text(json.dumps(payload),encoding='utf-8')
        checks[name]={'path':path.name,'sha256':sha256_file(path)}
    path=tmp_path/'release.json';path.write_text(json.dumps({'source_root':str(tmp_path),'checks':checks}),encoding='utf-8')
    report=validate_release(path)
    assert report['engineering_pass']
    assert not report['live_loop_pass'] and not report['research_pass'] and not report['external_pass']
    source.write_text('x=2\n',encoding='utf-8')
    assert not validate_release(path)['engineering_pass']


def test_moved_bundle_runs_new_assessment_and_preserves_identity(tmp_path):
    book = Workbook()
    book.active["A1"] = "READY"
    artifact = tmp_path / "answer.xlsx"
    book.save(artifact)
    source = tmp_path / "input.txt"
    source.write_text("frozen task input", encoding="utf-8")
    from workagent_rsi.artifact_assessment import spec_from_task
    from workagent_rsi.contracts import TaskSpec

    spec = spec_from_task(
        TaskSpec(
            task_id="replay",
            domain="excel",
            instruction="Review A1.",
            input_files=[str(source)],
        )
    )
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(spec.model_dump_json(), encoding="utf-8")
    record = dict(
        run_id="replay",
        git_commit="fixture",
        command=["offline"],
        exit_code=0,
        started_at="2026-10-26T00:00:00+00:00",
        ended_at="2026-10-26T00:00:01+00:00",
        identities={"assessment": SharedAssessment().identity()},
        files={"spec": spec_path, "artifact.xlsx": artifact, "input": source},
    )
    manifest = write_evidence_bundle(tmp_path / "original", record)
    shutil.move(str(manifest.parent), tmp_path / "moved")
    artifact.unlink()
    spec_path.unlink()
    source.unlink()
    report = replay_assessment_bundle(
        tmp_path / "moved" / "manifest.json",
        artifact_labels={"output": "artifact.xlsx"},
        input_labels={str(source): "input"},
    )
    assert report["fresh_assessment"] and report["identity_preserved"]
    assert report["old_score_reused"] is False
    assert report["assessment"]["judgement"] is None
    assert report["original_spec_hash"] != report["spec_hash"]
