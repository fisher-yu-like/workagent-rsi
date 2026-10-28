import pytest
from pptx import Presentation
from pptx.util import Inches
from pptx.oxml.xmlchemy import OxmlElement

from workagent_rsi.artifact_assessment import SharedAssessment, assessment_identity
from workagent_rsi.assessment_contracts import AcceptanceSpec, Requirement, Location
from workagent_rsi.check_registry import validate_acceptance_spec


POLICY = dict(min_text_shapes=1, min_shapes=1, min_connectors=0, forbid_images=True)


def spec(check='powerpoint.native_objects', expected=None, **scope):
    return AcceptanceSpec(task_id='native-controls', version='v1', artifacts={'output':'powerpoint'},
        dimension_weights={'content':1}, requirements=[Requirement(requirement_id='native',
        description='Independent structural control', check=check,
        expected=POLICY if expected is None else expected, location=Location(artifact='output', **scope),
        critical=True, dimension='content', evidence_source='Authored control')])


def deck(tmp_path):
    p=Presentation();slide=p.slides.add_slide(p.slide_layouts[6])
    slide.shapes.add_textbox(Inches(1),Inches(1),Inches(2),Inches(1)).text='Editable text'
    return p,slide,tmp_path/'output.pptx'


def result(p,path,value):
    p.save(path)
    return SharedAssessment().inspect(value, {'output':path}).checks[0]


def test_native_text_and_filename_are_separate_checks(tmp_path):
    p,s,path=deck(tmp_path)
    assert result(p,path,spec()).status=='PASS'
    assert result(p,path,spec('file.name','output.pptx')).status=='PASS'
    assert result(p,path,spec('file.name','different.pptx')).status=='FAIL'


@pytest.mark.parametrize('placement',['slide','group','master','layout','fill'])
def test_image_with_decoy_native_text_does_not_pass(tmp_path,placement):
    p,s,path=deck(tmp_path)
    root=s._element
    if placement=='group':root=s.shapes.add_group_shape()._element
    if placement=='master':root=s.slide_layout.slide_master._element
    if placement=='layout':root=s.slide_layout._element
    # Direct OOXML controls also cover images that the high-level shape parser
    # does not enumerate, including linked images and background fills.
    node=OxmlElement('a:blip');node.set('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}link','external-image')
    root.append(node)
    assert result(p,path,spec()).status=='FAIL'


def test_unknown_embedded_object_is_review_gap(tmp_path):
    p,s,path=deck(tmp_path)
    s.shapes._spTree.append(OxmlElement('p:oleObj'))
    row=result(p,path,spec())
    assert row.status=='NEEDS_REVIEW' and row.completion is None


def test_blank_and_wrong_slide_cannot_pass(tmp_path):
    p,s,path=deck(tmp_path);p.slides.add_slide(p.slide_layouts[6])
    assert result(p,path,spec(slide=2)).status=='FAIL'
    assert result(p,path,spec(slide=3)).status=='FAIL'
    assert result(p,path,spec(expected={**POLICY,'min_connectors':1})).status=='FAIL'


def test_grouped_native_shapes_count(tmp_path):
    p,s,path=deck(tmp_path)
    s.shapes.add_group_shape().shapes.add_textbox(0,0,1000,1000).text='Grouped editable text'
    assert result(p,path,spec(expected={**POLICY,'min_text_shapes':2,'min_shapes':2})).status=='PASS'


@pytest.mark.parametrize('value',['../output.pptx','D:\\output.pptx','output.pptx/','output.pptx.'])
def test_filename_spec_rejects_paths(value):
    assert validate_acceptance_spec(spec('file.name',value),{}).status=='SPEC_INCOMPLETE'


def test_policy_and_scope_are_strict():
    assert validate_acceptance_spec(spec(expected={**POLICY,'min_shapes':True}),{}).status=='SPEC_INCOMPLETE'
    assert validate_acceptance_spec(spec(object_id=1,slide=1),{}).status=='SPEC_INCOMPLETE'


def test_new_checker_participates_in_evaluator_identity(monkeypatch):
    from workagent_rsi import artifact_assessment as module
    original=module.sha256_file
    before=assessment_identity()
    monkeypatch.setattr(module,'sha256_file',lambda p:'changed' if p.name=='native_presentation_checks.py' else original(p))
    assert assessment_identity()!=before
