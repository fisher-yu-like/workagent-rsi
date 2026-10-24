"""Grounded repair wording and bounded projection of advice metadata."""
import re

from .assessment_contracts import Location


INTERNAL_KNOBS=re.compile(r'\b(?:sales_rows|sales_chart|sales_number_format|marker_source)\b',re.I)
GENERIC_REPAIR='Recompute the affected content from authorized inputs and recheck the frozen requirement.'


def safe_advice(text, *, qualification_only=False):
    if not isinstance(text,str):
        return GENERIC_REPAIR
    return GENERIC_REPAIR if INTERNAL_KNOBS.search(text) and not qualification_only else text


def repair_description(check):
    if check=='preservation':
        return 'Restore unauthorized changes from the frozen source and retain only the permitted edits.'
    if check in {'excel.cell','excel.range','excel.recalculated_value','excel.cached_value','facts.consistent'}:
        return 'Recompute the declared values from authorized source records and update the affected cells or facts.'
    if check in {'excel.formula','excel.formula_exact','excel.formula_present'}:
        return 'Correct the formula at the declared cell using the authorized inputs and required formula policy.'
    if check=='excel.chart' or check=='powerpoint.chart_values':
        return 'Correct the chart data and category references at the declared scope, then recheck their values.'
    if check=='excel.number_format':
        return 'Apply the required number format to the declared cells while preserving their values.'
    if check in {'word.headings','word.heading_style'}:
        return 'Correct the heading text, order or style within the requested scope.'
    if check in {'word.paragraph','word.table_cell','powerpoint.object_text','powerpoint.texts','text.contains'}:
        return 'Revise the requested text scope so the required content appears at that location.'
    if check=='powerpoint.bounds':
        return 'Place the affected required objects inside the slide canvas and recheck their rendered appearance.'
    if check=='semantic':
        return 'Revise the cited content against the frozen rubric and authorized source facts, retaining supported claims.'
    if check=='visual':
        return 'Adjust the affected layout using the cited real rendered regions and recheck every required page.'
    if check in {'file.readable','file.format'}:
        return 'Produce a genuine readable artifact in the declared Office format and recheck its required content.'
    return 'Correct the affected declared structure or content using the frozen requirement and authorized inputs.'


def public_issue_advice(issue):
    """Do not turn historical fixture knobs or nested metadata into general advice."""
    clean=dict(issue)
    qualification=clean.get('qualification_only') is True
    if 'qualification_only' in clean:
        clean['qualification_only']=qualification
    if 'skill_improvement_hint' in clean:
        clean['skill_improvement_hint']=safe_advice(clean['skill_improvement_hint'],qualification_only=True) if qualification and clean.get('skill_improvement_hint') else None
    if 'repair_hint' in clean:
        clean['repair_hint']=safe_advice(clean['repair_hint'],qualification_only=qualification)
    location_fields=set(Location.model_fields)
    def location(value):
        return {k:v for k,v in value.items() if k in location_fields} if isinstance(value,dict) else {}
    for key in ('location','requested_location'):
        if clean.get(key) is not None:
            clean[key]=location(clean[key])
    if 'observed_locations' in clean:
        values=clean['observed_locations'] if isinstance(clean['observed_locations'],list) else []
        clean['observed_locations']=[location(v) for v in values if isinstance(v,dict)]
    if isinstance(clean.get('repair_action'),dict):
        action=clean['repair_action']
        clean['repair_action']={k:v for k,v in action.items() if k in {'target','description','locations','evidence_refs'}}
        if 'description' in action:
            clean['repair_action']['description']=safe_advice(action['description'],qualification_only=qualification)
        if 'locations' in action:
            values=action['locations'] if isinstance(action['locations'],list) else []
            clean['repair_action']['locations']=[location(v) for v in values if isinstance(v,dict)]
    if 'verification_steps' in clean:
        values=clean['verification_steps'] if isinstance(clean['verification_steps'],list) else []
        clean['verification_steps']=[safe_advice(s,qualification_only=qualification) for s in values]
    return clean
