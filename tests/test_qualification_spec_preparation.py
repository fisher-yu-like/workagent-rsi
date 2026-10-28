import json
from pathlib import Path

import pytest

from test_benchmark_blind_pack import load_script
from workagent_rsi.contracts import TaskSpec
from workagent_rsi.hashing import canonical_json_hash, sha256_file


def test_source_spans_keep_all_instructions_and_do_not_claim_unsupported_word_checks(tmp_path):
    module=load_script('prepare_qualification_specs.py')
    source=tmp_path/'source.txt';source.write_text('Source information',encoding='utf-8')
    instruction="Change 'Acme Inc.' to 'New Co.' throughout. Keep the original bold formatting.\n1. Delete comment #0.\n2. Keep all blank lines."
    task=TaskSpec(task_id='word-test',domain='word',instruction=instruction,input_files=[str(source)])
    draft=module.draft_task(task)
    assert all(instruction[o['start']:o['end']]==o['source_quote'] for o in draft['obligations'])
    assert not draft['spec']['requirement_inventory']['reviewed']
    assert draft['spec']['requirement_inventory']['provenance']['reviewer'] is None
    assert draft['admission']['status']=='SPEC_INCOMPLETE'
    gaps=[o for o in draft['obligations'] if o['proposed_method']=='uncovered']
    assert len(gaps)==3 and all(not o['check_ids'] for o in gaps)
    assert not draft['live_ready']


def task_bundle(tmp_path):
    splits={};families=[]
    for split in ('develop','regression','hidden','ood_transfer'):
        rows=[]
        for domain in ('excel','word','powerpoint'):
            identity=split+'-'+domain;source=tmp_path/(identity+'.txt');source.write_text(identity,encoding='utf-8')
            companion=tmp_path/(identity+'-extra.txt');companion.write_text(identity+' supplemental source',encoding='utf-8')
            inputs=[source,companion]
            task=TaskSpec(task_id=identity,domain=domain,instruction='Preserve the supplied source facts.',input_files=[str(p) for p in inputs])
            digest=canonical_json_hash(sorted(sha256_file(p) for p in inputs))
            families.append(dict(base_task_id=identity,family_id=identity,source_document_id=identity,
                variant_ids=[identity],domain=domain,split='promotion_validation' if split=='hidden' else split,
                source_hash=digest,source_refs=['authored fixture'],variant_input_hashes={identity:digest}))
            rows.append(task.model_dump(mode='json'))
        splits[split]=rows
    path=tmp_path/'tasks.json';path.write_text(json.dumps({'splits':splits,'family_manifest':families}),encoding='utf-8')
    return path


def test_ppt_filename_is_covered_but_native_presence_cannot_approve_reconstruction(tmp_path):
    module=load_script('prepare_qualification_specs.py')
    source=tmp_path/'source.txt';source.write_text('Public reference',encoding='utf-8')
    task=TaskSpec(task_id='ppt-structure',domain='powerpoint',input_files=[str(source)],instruction=
        'Reconstruct one editable PowerPoint slide. Use native editable text, shapes and connectors; preserve semantics. '
        'No external raster resources are authorized. Save the result as output.pptx.')
    draft=module.draft_task(task)
    checks={r['check'] for r in draft['spec']['requirements']}
    assert {'file.name','powerpoint.native_objects'}<=checks
    assert draft['admission']['status']=='SPEC_INCOMPLETE'
    assert not draft['spec']['requirement_inventory']['reviewed']
    assert any(o['proposed_method']=='uncovered' for o in draft['obligations'])
    assert sum(o['proposed_method']=='deterministic' for o in draft['obligations'])==1


def test_all_inputs_are_frozen_before_drafts_and_drafts_cannot_self_approve(tmp_path):
    module=load_script('prepare_qualification_specs.py');bundle=task_bundle(tmp_path)
    report=module.prepare(bundle,tmp_path/'drafts')
    assert report['task_count']==12 and report['admission_counts']=={'SPEC_INCOMPLETE':12}
    assert report['model_calls']==report['server_jobs']==report['reviewer_signatures_created']==0
    ppt=next(r for r in report['tasks'] if r['domain']=='powerpoint')
    spec=json.loads((tmp_path/'drafts'/ppt['draft_file']).read_text(encoding='utf-8'))['spec']
    assert 'single-slide' not in {r['requirement_id'] for r in spec['requirements']}
    (tmp_path/'develop-excel.txt').write_text('modified',encoding='utf-8')
    with pytest.raises(ValueError,match='frozen family input hash differs'):
        module.prepare(bundle,tmp_path/'rejected')
    assert not (tmp_path/'rejected').exists()
