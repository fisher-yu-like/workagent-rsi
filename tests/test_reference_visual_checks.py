from PIL import Image

from test_visual_assessment import FakeRenderer, artifact, spec
from workagent_rsi.judgement_provider import VisualAssessmentChannel,VisualJudgement
from workagent_rsi.hashing import sha256_file
from workagent_rsi.check_registry import validate_acceptance_spec


class Judge:
    def __init__(self,omit_reference=False):self.calls=[];self.omit_reference=omit_reference
    def identity_config(self):return {'provider':'authored-reference-protocol-control'}
    def judge(self,request,work):
        self.calls.append(request)
        return VisualJudgement(status='PASS',completion=1,observed='Protocol control only',observations=[
            dict(image_id=i['image_id'],artifact_location=i['artifact_location'],region='all',observation='Attached image cited')
            for i in request['images'] if not self.omit_reference or not i['image_id'].startswith('reference-')]),{'model_calls':1}


def setup(tmp_path,omit=False):
    ref=tmp_path/'reference.png';Image.new('RGB',(31,20),'green').save(ref)
    r=spec().requirements[0].model_copy(update={'options':{'pages':[1,2,3],'reference_images':[{'path':str(ref),'sha256':sha256_file(ref)}]}})
    j=Judge(omit);c=VisualAssessmentChannel(FakeRenderer(tmp_path/'render',pages=3),j,tmp_path/'cache',max_images_per_check=2)
    return c,j,r,ref,artifact(tmp_path)


def test_reference_attached_to_every_batch_and_consumes_image_budget(tmp_path):
    c,j,r,ref,path=setup(tmp_path)
    result=c.check(r,path,sha256_file(path))
    assert result['status']=='PASS' and len(j.calls)==3
    assert all(len(q['images'])==2 and q['images'][-1]['image_id']=='reference-1' for q in j.calls)
    assert result['telemetry']['coverage']['checked_pages']==[1,2,3]


def test_missing_reference_citation_does_not_pass(tmp_path):
    c,j,r,ref,path=setup(tmp_path,True)
    assert c.check(r,path,sha256_file(path))['status']=='NEEDS_REVIEW'


def test_changed_reference_is_rejected_before_render_or_model_even_with_cache(tmp_path):
    c,j,r,ref,path=setup(tmp_path)
    assert c.check(r,path,sha256_file(path))['status']=='PASS'
    Image.new('RGB',(31,20),'red').save(ref)
    assert c.check(r,path,sha256_file(path))['status']=='NEEDS_REVIEW'
    assert len(j.calls)==3


def test_reference_requires_frozen_input_binding_in_preflight(tmp_path):
    c,j,r,ref,path=setup(tmp_path)
    s=spec().model_copy(update={'requirements':[r]})
    caps={'renderer':True,'visual_judge':True}
    assert validate_acceptance_spec(s,caps).status=='SPEC_INCOMPLETE'
    s=s.model_copy(update={'input_hashes':{str(ref):sha256_file(ref)}})
    assert validate_acceptance_spec(s,caps).status=='PASS'


def test_image_changed_during_judgement_cannot_be_cached_as_pass(tmp_path):
    c,j,r,ref,path=setup(tmp_path);original=j.judge
    def mutate(request,work):
        result=original(request,work);Image.new('RGB',(31,20),'red').save(ref);return result
    j.judge=mutate
    result=c.check(r,path,sha256_file(path))
    assert result['status']=='ERROR' and result['completion'] is None
    assert not list((tmp_path/'cache').rglob('cache.json'))
