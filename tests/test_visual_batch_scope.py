"""Regression from actual 17-page review: batch requests overstated their scope."""
from workagent_rsi.hashing import canonical_json_hash,sha256_file
from workagent_rsi.judgement_provider import VisualJudgement,VisualAssessmentChannel
from test_visual_assessment import FakeRenderer,artifact
from test_visibility_checks import long_visual


class ScopeAwareJudge:
    def __init__(self,last_page_defect=False):self.calls=[];self.last_page_defect=last_page_defect
    def identity_config(self):return {'provider':'authored-scope-contract-only'}
    def judge(self,request,work):
        self.calls.append(request)
        pages=[int(i['image_id'].split('-')[-1]) for i in request['images']]
        missing=set(request['requirement']['options']['pages'])-set(pages)
        status='NEEDS_REVIEW' if missing else 'FAIL' if self.last_page_defect and 17 in pages else 'PASS'
        return VisualJudgement(status=status,completion=None if missing else 0 if status=='FAIL' else 1,
            observed='Authored missing-input scope response' if missing else 'Authored scope control',
            observations=[{'image_id':i['image_id'],'artifact_location':i['artifact_location'],'region':'message region',
                'observation':'Authored protocol citation, not visual accuracy'} for i in request['images']]),{'model_calls':1}


def test_clean_long_deck_is_not_unknown_because_other_batches_are_absent(tmp_path):
    judge=ScopeAwareJudge();channel,req,path=long_visual(tmp_path,judge)
    before=req.model_dump(mode='json')
    result=channel.check(req,path,sha256_file(path))
    assert result['status']=='PASS'
    assert req.model_dump(mode='json')==before
    assert result['telemetry']['coverage']['checked_pages']==list(range(1,18))
    assert [c['requirement']['options']['pages'] for c in judge.calls]==[list(range(1,9)),list(range(9,17)),[17]]
    assert all(c['batch_scope']['required_pages']==list(range(1,18)) for c in judge.calls)
    assert all(c['batch_scope']['global_requirement_hash']==canonical_json_hash(before) for c in judge.calls)


def test_last_page_defect_is_retained_without_spurious_missing_batch_review(tmp_path):
    judge=ScopeAwareJudge(last_page_defect=True);channel,req,path=long_visual(tmp_path,judge)
    result=channel.check(req,path,sha256_file(path))
    assert result['status']=='FAIL' and result['completion']==0
    assert result['telemetry']['coverage']['complete'] is True
    assert len(judge.calls)==3


def test_joint_consistency_scope_contains_only_attached_pages(tmp_path):
    judge=ScopeAwareJudge();channel,req,path=long_visual(tmp_path,judge)
    channel=VisualAssessmentChannel(FakeRenderer(tmp_path/'small-render',pages=3),judge,tmp_path/'cache-small',max_images_per_check=2)
    req=req.model_copy(update={'options':{'pages':[1,2,3],'cross_partition_consistency':True,'consistency_groups':[[1,2],[2,3]]}})
    result=channel.check(req,path,sha256_file(path))
    assert result['status']=='PASS' and result['telemetry']['consistency_complete']
    assert [r['requirement']['options']['pages'] for r in judge.calls]==[[1,2],[3],[1,2],[2,3]]
    assert [r['requirement']['options']['consistency_groups'] for r in judge.calls]==[[],[],[[1,2]],[[2,3]]]


def test_old_unscoped_cache_does_not_supply_new_protocol_decisions(tmp_path,monkeypatch):
    judge=ScopeAwareJudge();channel,req,path=long_visual(tmp_path,judge,cache=True)
    current=channel.identity_config
    old={**current(),'coverage_protocol':'all-required-pages-batched-v1'}
    monkeypatch.setattr(channel,'identity_config',lambda:old)
    channel.check(req,path,sha256_file(path))
    assert len(judge.calls)==3
    monkeypatch.setattr(channel,'identity_config',current)
    channel.check(req,path,sha256_file(path))
    assert len(judge.calls)==6
