"""Conservative slide geometry risks and explicit rendered-page coverage."""

from typing import Literal

from pydantic import Field, model_validator

from .assessment_contracts import AssessmentModel


class VisibilityFinding(AssessmentModel):
    object_id: int
    kind: str
    certainty: Literal['certain', 'risk']
    evidence: str


class VisualCoverageLedger(AssessmentModel):
    required_pages: list[int] = Field(min_length=1)
    rendered_pages: list[int]
    checked_pages: list[int]

    @model_validator(mode='after')
    def validate_pages(self):
        for pages in (self.required_pages, self.rendered_pages, self.checked_pages):
            if any(type(p) is not int or p < 1 for p in pages) or len(pages) != len(set(pages)):
                raise ValueError('page identities must be unique positive integers')
        if not set(self.checked_pages) <= set(self.rendered_pages):
            raise ValueError('checked pages must have a rendering')
        return self

    @property
    def complete(self):
        return set(self.required_pages) <= set(self.rendered_pages) & set(self.checked_pages)

    def report(self):
        return {**self.model_dump(mode='json'), 'complete': self.complete,
                'missing_render_pages': sorted(set(self.required_pages) - set(self.rendered_pages)),
                'unchecked_pages': sorted(set(self.required_pages) - set(self.checked_pages))}


def inspect_visibility(deck, slide_index):
    """Geometry is a risk filter, not a substitute for rendered inspection.

    Flatten group transforms into slide coordinates. Shape order is paint order;
    a background behind content is legal, a later intersecting fill is uncertain.
    Rotation, alpha and theme-dependent colours require rendered review.
    """
    if not 1 <= slide_index <= len(deck.slides):
        raise ValueError('slide is missing')
    rows, findings = [], []

    def walk(shapes, sx=1., sy=1., tx=0., ty=0., rotated=False):
        for shape in shapes:
            rotation = rotated or bool(shape.rotation)
            if hasattr(shape, 'shapes'):
                xfrm = shape._element.grpSpPr.xfrm
                if xfrm is None or not xfrm.chExt.cx or not xfrm.chExt.cy:
                    findings.append(VisibilityFinding(object_id=shape.shape_id, kind='group_transform',
                        certainty='risk', evidence='group coordinate transform is unavailable'))
                    continue
                gx, gy = shape.width / xfrm.chExt.cx, shape.height / xfrm.chExt.cy
                walk(shape.shapes, sx*gx, sy*gy,
                     tx+sx*(shape.left-gx*xfrm.chOff.x), ty+sy*(shape.top-gy*xfrm.chOff.y), rotation)
            else:
                rows.append((shape, (tx+sx*shape.left, ty+sy*shape.top,
                                     tx+sx*(shape.left+shape.width), ty+sy*(shape.top+shape.height)), rotation))
    walk(deck.slides[slide_index-1].shapes)
    for index, (shape, bounds, rotated) in enumerate(rows):
        left, top, right, bottom = bounds
        if left < 0 or top < 0 or right > deck.slide_width or bottom > deck.slide_height:
            findings.append(VisibilityFinding(object_id=shape.shape_id, kind='off_canvas',
                certainty='risk' if rotated else 'certain', evidence=f'slide-space bounds={bounds}'))
        if rotated:
            findings.append(VisibilityFinding(object_id=shape.shape_id, kind='rotation', certainty='risk',
                evidence='rotated shape/group requires rendered inspection'))
        if shape._element.xpath('.//a:alpha | .//a:alphaMod | .//a:alphaModFix | .//p:cNvPr[@hidden="1"]'):
            findings.append(VisibilityFinding(object_id=shape.shape_id, kind='opacity_or_hidden', certainty='risk',
                evidence='explicit alpha/hidden attributes require rendered inspection'))
        # Only objects that carry content can be obscured. An earlier empty
        # background containing later content is not an occlusion finding.
        content = bool(getattr(shape, 'has_table', False) or getattr(shape, 'has_chart', False)
                       or getattr(shape, 'text', '').strip() or shape.shape_type == 13)
        if not content:
            continue
        for front, box, _ in rows[index+1:]:
            intersects = max(left, box[0]) < min(right, box[2]) and max(top, box[1]) < min(bottom, box[3])
            fill = getattr(front, 'fill', None)
            filled = fill is not None and fill.type is not None and int(fill.type) != 5
            foreground_content = bool(getattr(front, 'text', '').strip() or getattr(front, 'has_table', False)
                                      or getattr(front, 'has_chart', False) or front.shape_type == 13)
            inherited_shape_fill = front.shape_type == 1 and fill is not None and fill.type is None
            if intersects and (filled or foreground_content or inherited_shape_fill):
                findings.append(VisibilityFinding(object_id=shape.shape_id, kind='possible_occlusion', certainty='risk',
                    evidence=f'later object {front.shape_id} intersects content; alpha/paint must be rendered'))
        if getattr(shape, 'has_text_frame', False):
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    color = run.font.color
                    if color.type is not None and int(color.type) == 1 and str(color.rgb) == 'FFFFFF':
                        findings.append(VisibilityFinding(object_id=shape.shape_id, kind='low_contrast', certainty='risk',
                            evidence='white text requires background/contrast inspection'))
                        break
    return findings
