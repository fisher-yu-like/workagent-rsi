"""Structural PowerPoint checks. Visual fidelity remains a separate obligation."""
from .artifact_locations import ScopeNotFound


def inspect_native_objects(deck, location, policy):
    if location.slide is not None and location.slide > len(deck.slides):
        raise ScopeNotFound('requested slide is missing')
    slides = [deck.slides[location.slide - 1]] if location.slide else list(deck.slides)
    counts = {'text_shapes': 0, 'shapes': 0, 'connectors': 0}
    images, unsupported = [], []
    for slide in slides:
        for element in slide.shapes._spTree.iter():
            name = element.tag.rsplit('}', 1)[-1]
            if name == 'sp':
                counts['shapes'] += 1
                if any(t.text and t.text.strip() for t in element.iter()
                       if t.tag == '{http://schemas.openxmlformats.org/drawingml/2006/main}t'):
                    counts['text_shapes'] += 1
            elif name == 'cxnSp':
                counts['connectors'] += 1
            elif name in {'oleObj', 'contentPart', 'AlternateContent'}:
                unsupported.append(name)
            elif name == 'graphicData' and element.get('uri') not in {
                    'http://schemas.openxmlformats.org/drawingml/2006/table',
                    'http://schemas.openxmlformats.org/drawingml/2006/chart'}:
                unsupported.append(element.get('uri', 'unknown graphicData'))
        # Inspect inherited fills as well: an image on the master cannot be
        # concealed by adding one native text box on the slide.
        for label, root in [('slide', slide._element),
                            ('layout', slide.slide_layout._element),
                            ('master', slide.slide_layout.slide_master._element),
                            *[('chart', shape.chart._chartSpace) for shape in _shapes(slide.shapes)
                              if shape.has_chart]]:
            for element in root.iter():
                if element.tag.rsplit('}', 1)[-1] in {'blip', 'svgBlip', 'imagedata', 'pic'}:
                    images.append(label)
    violations = [key for key, actual in counts.items() if actual < policy['min_' + key]]
    if policy['forbid_images'] and images:
        violations.append('images')
    observed = {'counts': counts, 'image_locations': images,
                'unsupported_objects': unsupported, 'violations': violations,
                'scope': 'native object structure only; not visual fidelity or full task acceptance'}
    if violations:
        return 'FAIL', 0, observed, location
    if unsupported:
        return 'NEEDS_REVIEW', None, observed, location
    return 'PASS', 1, observed, location


def _shapes(shapes):
    for shape in shapes:
        yield shape
        if hasattr(shape, 'shapes'):
            yield from _shapes(shape.shapes)
