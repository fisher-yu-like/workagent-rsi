"""Evidence-backed release levels and fresh, portable assessment replay."""
import json
from pathlib import Path
import re
import subprocess

from .hashing import sha256_file
from .evidence_bundle import verify_evidence_bundle

ENGINEERING_CHECKS=('full_pytest','compileall','diff_check','calibration_90','t01_regressions',
                    'moved_bundle_replay','credential_scan','linux_non_com')


def validate_release(manifest: Path) -> dict:
    manifest=Path(manifest)
    data=json.loads(manifest.read_text(encoding='utf-8'))
    def load(name):
        reference=data.get('checks',{}).get(name)
        if not isinstance(reference,dict):return None
        from .view_safety import relative_reference, ordinary_file
        try:
            path=ordinary_file(manifest.parent/relative_reference(reference['path']))
            if sha256_file(path)!=reference['sha256']:return None
            return json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError,KeyError):return None
    checks={}
    for name in ENGINEERING_CHECKS:
        receipt=load(name)
        checks[name]=bool(receipt and type(receipt.get('exit_code')) is int and receipt['exit_code']==0)
        if name=='full_pytest' and checks[name]:
            cases=receipt.get('cases',[])
            checks[name]=bool(cases) and all(c['status'] in {'passed','skipped'} for c in cases)
        if name=='calibration_90' and checks[name]:
            checks[name]=receipt.get('case_count')==90 and receipt.get('known_critical_false_accepts')==0 and receipt.get('permitted_equivalent_false_rejects')==0
        if name=='moved_bundle_replay' and checks[name]:
            checks[name]=receipt.get('fresh_assessment') is True and receipt.get('identity_preserved') is True
        if name=='credential_scan' and checks[name]:checks[name]=receipt.get('findings')==[]
        if name=='linux_non_com' and checks[name]:checks[name]=receipt.get('platform')=='linux' and receipt.get('actual_execution') is True
    # A test run from another source snapshot cannot qualify this release.
    full=load('full_pytest')
    source_root=data.get('source_root')
    if checks['full_pytest']:
        if not source_root or not full.get('source_hashes'):
            checks['full_pytest']=False
        else:
            source_root=Path(source_root)
            checks['full_pytest']=all((source_root/p).is_file() and sha256_file(source_root/p)==digest
                                       for p,digest in full['source_hashes'].items())
    engineering=all(checks.values())
    live=load('live_qualification')
    human=load('human_calibration')
    cohort=load('research_cohort')
    study=load('four_arm_study')
    external=load('external_admission')
    live_pass=engineering and bool(live and live.get('actual_execution') is True
                                  and live.get('three_domain_repair_complete') is True and live.get('outer_loop_complete') is True)
    research=live_pass and bool(human and human.get('human_labels',0)>=32 and human.get('judge_calibration_pass') is True
        and cohort and cohort.get('sealed_final_complete') is True and study and study.get('all_arms_complete') is True
        and study.get('statistical_protocol_pass') is True)
    external_pass=research and bool(external and external.get('formal_ready') is True
                                   and external.get('actual_native_run') is True)
    return {'schema_version':'release-gates-v2','engineering_pass':engineering,'live_loop_pass':live_pass,
        'research_pass':research,'external_pass':external_pass,'checks':checks,
        'blocked_checks':[name for name,passed in checks.items() if not passed],
        'pending_claims':[name for name,passed in [('live_loop',live_pass),('research',research),('external',external_pass)] if not passed]}


def replay_assessment_bundle(manifest, *, spec_label='spec', artifact_labels=None, input_labels=None, assessment=None):
    from .artifact_assessment import SharedAssessment
    from .assessment_contracts import AcceptanceSpec
    files=verify_evidence_bundle(Path(manifest))
    metadata=json.loads(Path(manifest).read_text(encoding='utf-8'))
    spec=AcceptanceSpec.model_validate_json(files[spec_label].read_text(encoding='utf-8'))
    original_spec_hash=spec.fingerprint()
    rebindings={}
    if spec.input_hashes:
        if set(input_labels or {})!=set(spec.input_hashes):
            raise ValueError('portable replay requires an explicit label for every frozen input')
        for old_path,label in input_labels.items():
            source=files[label]
            if sha256_file(source)!=spec.input_hashes[old_path]:
                raise ValueError('bundled input differs from frozen specification')
            rebindings[old_path]=str(source.resolve())
        # Only locations change. Each replacement retains the exact frozen hash;
        # report both spec hashes and the relocation map rather than claiming
        # path-sensitive spec identity is unchanged.
        spec=AcceptanceSpec.model_validate({**spec.model_dump(mode='json'),
            'input_hashes':{rebindings[p]:digest for p,digest in spec.input_hashes.items()}})
    inspector=assessment or SharedAssessment()
    paths={name:files[label] for name,label in (artifact_labels or {'output':'artifact'}).items()}
    result=inspector.inspect(spec,paths)
    return {'exit_code':0,'fresh_assessment':True,
            'identity_preserved':inspector.identity()==metadata.get('identities',{}).get('assessment'),
            'assessment_identity':inspector.identity(),'spec_hash':spec.fingerprint(),
            'original_spec_hash':original_spec_hash,'input_rebindings':rebindings,
            'artifact_hashes':{name:sha256_file(path) for name,path in paths.items()},
            'assessment':result.model_dump(mode='json'),'old_score_reused':False}


def scan_tracked_credentials(root):
    root=Path(root)
    names=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode('utf-8').split('\0')
    rules={'private_key':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
           'service_token':re.compile(r'\b(?:sk-(?:proj-|svcacct-)?|ghp_)[A-Za-z0-9_-]{32,}\b')}
    findings=[]
    for name in filter(None,names):
        path=root/name
        if not path.is_file() or path.stat().st_size>5_000_000:continue
        body=path.read_bytes().decode('utf-8',errors='replace')
        for rule,pattern in rules.items():
            if pattern.search(body):findings.append({'path':name,'rule':rule})
    return {'exit_code':1 if findings else 0,'findings':findings,
            'scope':'Tracked files up to 5 MB; pattern scan, not a guarantee of credential absence.'}
