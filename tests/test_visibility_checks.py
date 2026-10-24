import importlib
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor
import pytest

from workagent_rsi.artifact_assessment import assess
from workagent_rsi.assessment_contracts import AcceptanceSpec,Requirement,Location


def spec(check='powerpoint.texts',expected=None):
    return AcceptanceSpec(task_id='visible',version='authored-v1',artifacts={'output':'powerpoint'},dimension_weights={'content':1},
        requirements=[Requirement(requirement_id='visible',description='Required content must be visible',check=check,
            expected=['Required'] if expected is None else expected,location=Location(artifact='output',slide=1),
            critical=True,dimension='content',evidence_source='authored geometry')])


def deck(tmp_path,kind):
    prs=Presentation();slide=prs.slides.add_slide(prs.slide_layouts[6])
    if kind=='background':
        bg=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,0,0,prs.slide_width,prs.slide_height);bg.fill.solid();bg.fill.fore_color.rgb=RGBColor(255,255,255)
    shape=slide.shapes.add_textbox(Inches(1),Inches(1),Inches(2),Inches(.5));shape.text='Required'
    if kind=='outside':shape.left=prs.slide_width+1
    if kind=='rotated':shape.rotation=45
    if kind=='white':shape.text_frame.paragraphs[0].runs[0].font.color.rgb=RGBColor(255,255,255)
    if kind=='covered':
        cover=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,0,0,Inches(5),Inches(3));cover.fill.solid();cover.fill.fore_color.rgb=RGBColor(255,255,255)
    path=tmp_path/'deck.pptx';prs.save(path);return prs,path


def test_off_canvas_required_content_is_not_accepted(tmp_path):
    _,path=deck(tmp_path,'outside');shared,score,_=assess(spec(),{'output':path})
    assert shared.checks[0].status=='FAIL' and score.acceptance_status=='FAIL'


def test_opaque_containment_is_not_automatic_pass(tmp_path):
    _,path=deck(tmp_path,'covered');shared,score,_=assess(spec('powerpoint.overlap',[]),{'output':path})
    assert shared.checks[0].status=='NEEDS_REVIEW' and score.total_score is None


def test_required_text_under_cover_needs_review(tmp_path):
    _,path=deck(tmp_path,'covered')
    assert assess(spec(),{'output':path})[0].checks[0].status=='NEEDS_REVIEW'


def test_legal_background_is_not_automatic_failure(tmp_path):
    _,path=deck(tmp_path,'background')
    assert assess(spec('powerpoint.overlap',[]),{'output':path})[0].checks[0].status=='PASS'


@pytest.mark.parametrize('kind',['white','rotated'])
def test_uncertain_visibility_is_review_risk_not_quality_pass(tmp_path,kind):
    _,path=deck(tmp_path,kind)
    assert assess(spec(),{'output':path})[0].checks[0].status=='NEEDS_REVIEW'


def test_findings_distinguish_certain_overflow_and_visual_risk(tmp_path):
    module=importlib.import_module('workagent_rsi.visibility_checks');prs,_=deck(tmp_path,'outside')
    rows=module.inspect_visibility(prs,1)
    assert any(r.kind=='off_canvas' and r.certainty=='certain' for r in rows)


def test_group_coordinates_are_transformed_to_slide_space(tmp_path):
    module=importlib.import_module('workagent_rsi.visibility_checks');prs=Presentation();slide=prs.slides.add_slide(prs.slide_layouts[6])
    group=slide.shapes.add_group_shape();shape=group.shapes.add_textbox(0,0,10,10);shape.text='Required'
    group.left=prs.slide_width+100
    assert any(r.object_id==shape.shape_id and r.kind=='off_canvas' for r in module.inspect_visibility(prs,1))


@pytest.mark.parametrize('rendered,checked,complete',[([1,2],[1,2],True),([1],[1],False),([1,2],[1],False)])
def test_unchecked_required_page_blocks_visual_completion(rendered,checked,complete):
    from workagent_rsi.visibility_checks import VisualCoverageLedger
    ledger=VisualCoverageLedger(required_pages=[1,2],rendered_pages=rendered,checked_pages=checked)
    assert ledger.complete is complete


def test_checked_page_without_render_is_invalid():
    from workagent_rsi.visibility_checks import VisualCoverageLedger
    with pytest.raises(ValueError):VisualCoverageLedger(required_pages=[1],rendered_pages=[],checked_pages=[1])


class AuthoredProvider:
    def __init__(self,*,miss_last=False,fail_last=False):self.calls=[];self.miss_last=miss_last;self.fail_last=fail_last
    def identity_config(self):return {'provider':'authored-page-coverage-unit-fixture'}
    def judge(self,request,work):
        from workagent_rsi.judgement_provider import VisualJudgement
        self.calls.append(request)
        images=request['images'];last=any(i['image_id']=='page-17' for i in images)
        if self.fail_last and last:return None,{'status':'unavailable','error':'authored last-batch failure','model_calls':0}
        selected=images[:-1] if self.miss_last and last else images
        return VisualJudgement(status='PASS',completion=1,observed='Authored mapping fixture',observations=[
            {'image_id':i['image_id'],'artifact_location':i['artifact_location'],'region':'whole page','observation':'Authored citation only'} for i in selected]),{'model_calls':1}


def long_visual(tmp_path,provider,*,cache=False):
    from test_visual_assessment import FakeRenderer,artifact
    from workagent_rsi.judgement_provider import VisualAssessmentChannel
    path=artifact(tmp_path)
    channel=VisualAssessmentChannel(FakeRenderer(tmp_path/'render',pages=17),provider,tmp_path/'cache',max_images_per_check=8,cache_enabled=cache)
    req=Requirement(requirement_id='all-pages',description='Inspect all required pages',check='visual',
        location=Location(artifact='output'),dimension='content',evidence_source='authored coverage',options={'pages':list(range(1,18))})
    return channel,req,path


def test_long_visual_batches_cover_all_required_pages(tmp_path):
    from workagent_rsi.hashing import sha256_file
    provider=AuthoredProvider();channel,req,path=long_visual(tmp_path,provider)
    result=channel.check(req,path,sha256_file(path))
    assert result['status']=='PASS' and [len(c['images']) for c in provider.calls]==[8,8,1]
    assert result['telemetry']['coverage']['complete'] is True
    assert result['telemetry']['coverage']['checked_pages']==list(range(1,18))


def test_last_batch_missing_citation_prevents_pass(tmp_path):
    from workagent_rsi.hashing import sha256_file
    provider=AuthoredProvider(miss_last=True);channel,req,path=long_visual(tmp_path,provider)
    result=channel.check(req,path,sha256_file(path))
    assert result['status']!='PASS' and result['completion'] is None
    assert result['telemetry']['coverage']['complete'] is False


def test_last_batch_capability_failure_retains_prior_coverage(tmp_path):
    from workagent_rsi.hashing import sha256_file
    provider=AuthoredProvider(fail_last=True);channel,req,path=long_visual(tmp_path,provider)
    result=channel.check(req,path,sha256_file(path))
    assert result['status']=='UNAVAILABLE' and result['telemetry']['coverage']['checked_pages']==list(range(1,17))


def test_cache_reuses_batches_without_independent_model_calls(tmp_path):
    from workagent_rsi.hashing import sha256_file
    provider=AuthoredProvider();channel,req,path=long_visual(tmp_path,provider,cache=True)
    first=channel.check(req,path,sha256_file(path));second=channel.check(req,path,sha256_file(path))
    assert first['status']==second['status']=='PASS' and len(provider.calls)==3
    assert second['telemetry']['model_calls']==0 and second['telemetry']['coverage']['complete']


def test_transparent_text_requires_review(tmp_path):
    from pptx.oxml.xmlchemy import OxmlElement
    prs,path=deck(tmp_path,'white')
    run=prs.slides[0].shapes[0].text_frame.paragraphs[0].runs[0]
    color=run._r.xpath('.//a:srgbClr')[0]
    alpha=OxmlElement('a:alpha');alpha.set('val','0');color.append(alpha)
    prs.save(path)
    assert assess(spec(),{'output':path})[0].checks[0].status=='NEEDS_REVIEW'


def test_clear_duplicate_can_satisfy_required_text(tmp_path):
    prs,path=deck(tmp_path,'outside')
    shape=prs.slides[0].shapes.add_textbox(Inches(1),Inches(1),Inches(2),Inches(.5));shape.text='Required'
    prs.save(path)
    assert assess(spec(),{'output':path})[0].checks[0].status=='PASS'


def test_image_only_slide_has_no_text_absence_defect(tmp_path):
    from PIL import Image
    from workagent_rsi.visibility_checks import inspect_visibility
    png=tmp_path/'authored.png';Image.new('RGB',(32,32),'blue').save(png)
    prs=Presentation();slide=prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_picture(str(png),Inches(1),Inches(1),Inches(2),Inches(2))
    assert inspect_visibility(prs,1)==[]


def test_reviewed_pages_remain_checked_even_when_quality_is_uncertain(tmp_path):
    class ReviewProvider(AuthoredProvider):
        def judge(self,request,work):
            decision,telemetry=super().judge(request,work)
            return decision.model_copy(update={'status':'NEEDS_REVIEW','completion':None}),telemetry
    from workagent_rsi.hashing import sha256_file
    provider=ReviewProvider();channel,req,path=long_visual(tmp_path,provider)
    result=channel.check(req,path,sha256_file(path))
    assert result['status']=='NEEDS_REVIEW' and result['completion'] is None
    assert len(provider.calls)==3 and result['telemetry']['coverage']['complete'] is True


def test_inherited_foreground_fill_is_a_review_risk(tmp_path):
    prs,path=deck(tmp_path,'background')
    prs.slides[0].shapes.add_shape(MSO_SHAPE.RECTANGLE,0,0,Inches(5),Inches(3))
    prs.save(path)
    assert assess(spec(),{'output':path})[0].checks[0].status=='NEEDS_REVIEW'


def test_corrupt_cached_batch_is_not_counted_as_checked(tmp_path):
    from workagent_rsi.hashing import sha256_file
    provider=AuthoredProvider();channel,req,path=long_visual(tmp_path,provider,cache=True)
    assert channel.check(req,path,sha256_file(path))['status']=='PASS'
    for cached in (tmp_path/'cache').glob('*/cache.json'):cached.write_text('{broken',encoding='utf-8')
    result=channel.check(req,path,sha256_file(path))
    assert result['status']=='ERROR' and result['telemetry']['model_calls']==0
    assert result['telemetry']['coverage']['checked_pages']==[]
