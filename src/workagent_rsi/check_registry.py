"""Registered deterministic/channel checks and side-effect-free spec preflight."""
from __future__ import annotations

import json
import re

from pydantic import Field

from .assessment_contracts import (AcceptanceSpec, AssessmentModel, Location,
    RequirementCoverage, SpecAdmissionReport, SpecFinding)


class CheckDefinition(AssessmentModel):
    name: str
    domains: list[str]
    required_location_fields: list[str] = Field(default_factory=list)
    expected_schema: str
    capabilities: list[str] = Field(default_factory=list)


ALL = ['excel','word','powerpoint']
_definitions = [
    ('file.readable',ALL,[],'boolean',[]),
    ('file.format',ALL,[],'domain',[]),
    ('file.name',ALL,[],'filename',[]),
    ('text.contains',ALL,[],'text',[]),
    ('excel.sheets',['excel'],[],'texts',[]),
    ('excel.cell',['excel'],['sheet','cell'],'scalar',[]),
    ('excel.formula',['excel'],['sheet','cell'],'formula',[]),
    ('excel.formula_exact',['excel'],['sheet','cell'],'formula',[]),
    ('excel.formula_present',['excel'],['sheet','cell'],'boolean',[]),
    ('excel.number_format',['excel'],['sheet','cell'],'text',[]),
    ('excel.range',['excel'],['sheet','cell'],'matrix',[]),
    ('excel.cached_value',['excel'],['sheet','cell'],'scalar',[]),
    ('excel.recalculated_value',['excel'],['sheet','cell'],'scalar',['spreadsheet_recalc']),
    ('excel.chart',['excel'],['sheet'],'chart_refs',[]),
    ('word.headings',['word'],[],'texts',[]),
    ('word.heading_style',['word'],['heading'],'text',[]),
    ('word.references',['word'],[],'texts',[]),
    ('word.paragraph',['word'],['paragraph'],'text',[]),
    ('word.table_cell',['word'],['table','row','column'],'text',[]),
    ('powerpoint.object_text',['powerpoint'],['slide','object_id'],'text',[]),
    ('powerpoint.slide_count',['powerpoint'],[],'count',[]),
    ('powerpoint.native_objects',['powerpoint'],[],'native_policy',[]),
    ('powerpoint.texts',['powerpoint'],[],'texts',[]),
    ('powerpoint.chart_values',['powerpoint'],['slide','object_id'],'matrix',[]),
    ('powerpoint.bounds',['powerpoint'],['slide'],'list',[]),
    ('powerpoint.overlap',['powerpoint'],['slide'],'list',[]),
    ('facts.consistent',ALL,[],'scalar',[]),
    ('visual',ALL,[],'any',['renderer','visual_judge']),
    ('semantic',ALL,[],'any',['semantic_judge']),
    ('preservation',ALL,[],'boolean',[]),
]
REGISTRY = {name:CheckDefinition(name=name,domains=domains,required_location_fields=fields,
    expected_schema=schema,capabilities=caps) for name,domains,fields,schema,caps in _definitions}

LEGACY_ADAPTERS = {'required_text':'text.contains','marker':'text.contains','output_format':'file.format',
    'required_sheets':'excel.sheets','required_cells':'excel.cell','required_formulas':'excel.formula',
    'required_formula_values':'excel.cached_value','required_headings':'word.headings',
    'required_heading_styles':'word.heading_style','required_slide_count':'powerpoint.slide_count',
    'required_slides':'powerpoint.slide_count','required_shape_text':'powerpoint.texts'}


def registry_manifest():
    return {name:REGISTRY[name].model_dump(mode='json') for name in sorted(REGISTRY)}


def legacy_adapter_coverage():
    return {key:{'check':name,'status':'supported','limits':'Requires valid expected type and explicit location where applicable.'}
            for key,name in sorted(LEGACY_ADAPTERS.items())}


def validate_location(location, domain, *, fact=False):
    """Configuration syntax only; object existence is an artifact observation."""
    loc = Location.model_validate(location)
    groups = {'excel':['sheet','cell'],'word':['paragraph','heading','table'],
              'powerpoint':['slide','object_id']}
    for other,fields in groups.items():
        if other != domain and any(getattr(loc,name) is not None for name in fields):
            raise ValueError('location belongs to a different artifact domain')
    if loc.cell is not None:
        if not loc.sheet or not re.fullmatch(r'\$?[A-Za-z]{1,3}\$?[1-9][0-9]*(?::\$?[A-Za-z]{1,3}\$?[1-9][0-9]*)?',loc.cell):
            raise ValueError('cell/range requires explicit sheet and valid Excel coordinates')
        from openpyxl.utils.cell import range_boundaries
        a,b,c,d = range_boundaries(loc.cell)
        if a>c or b>d or c>16384 or d>1048576:
            raise ValueError('Excel range is reversed or outside worksheet limits')
    if (loc.row is None) != (loc.column is None):
        raise ValueError('table scope needs both row and column')
    if loc.row is not None and ((domain=='word' and loc.table is None)
            or (domain=='powerpoint' and (loc.slide is None or loc.object_id is None)) or domain=='excel'):
        raise ValueError('table cell needs an explicit table/object location')
    if loc.object_id is not None and loc.slide is None:
        raise ValueError('object scope requires slide')
    if loc.group_path is not None and (domain!='powerpoint' or loc.slide is None):
        raise ValueError('group path requires an explicit PowerPoint slide')
    if domain=='word' and loc.table is not None and (loc.paragraph is not None or loc.heading is not None):
        raise ValueError('paragraph/heading and table selectors are conflicting')
    if fact:
        valid = (domain=='excel' and loc.sheet and loc.cell and ':' not in loc.cell
            or domain=='word' and (loc.paragraph or loc.table and loc.row and loc.column)
            or domain=='powerpoint' and loc.slide and loc.object_id is not None)
        if not valid:
            raise ValueError('fact check needs an exact cell/paragraph/table/object location')
    return loc


def _expected(value, schema):
    json.dumps(value, allow_nan=False)
    text = lambda v:isinstance(v,str) and bool(v.strip())
    valid = {
        'any':lambda:True, 'boolean':lambda:type(value) is bool,
        'domain':lambda:value in ALL if isinstance(value,str) else False,
        'text':lambda:text(value), 'formula':lambda:text(value) and value.startswith('='),
        'filename':lambda:text(value) and value not in {'.','..'} and not any(c in value for c in '/\\:*?"<>|') and value==value.strip() and not value.endswith('.'),
        'native_policy':lambda:isinstance(value,dict) and set(value)=={'min_text_shapes','min_shapes','min_connectors','forbid_images'}
            and all(type(value[k]) is int and value[k]>=0 for k in ('min_text_shapes','min_shapes','min_connectors'))
            and type(value['forbid_images']) is bool,
        'texts':lambda:isinstance(value,list) and bool(value) and all(text(v) for v in value),
        'scalar':lambda:value is None or type(value) in {str,int,float,bool},
        'count':lambda:type(value) is int and value>=0,
        'matrix':lambda:isinstance(value,list) and bool(value) and all(isinstance(row,list) and row for row in value)
            and len({len(row) for row in value})==1
            and all(v is None or type(v) in {str,int,float,bool} for row in value for v in row),
        'chart_refs':lambda:isinstance(value,list) and bool(value) and all(isinstance(v,dict)
            and set(v)=={'values','categories'} and all(text(x) for x in v.values()) for v in value),
        'list':lambda:isinstance(value,list),
    }[schema]()
    if not valid:
        raise ValueError('expected value does not match registered schema '+schema)


def validate_acceptance_spec(spec, capabilities) -> SpecAdmissionReport:
    findings = []
    def gap(rid,origin,message):
        findings.append(SpecFinding(requirement_id=rid,origin=origin,message=message))
    try:
        spec = AcceptanceSpec.model_validate(spec.model_dump(mode='json') if isinstance(spec,AcceptanceSpec) else spec)
    except (ValueError,TypeError) as exc:
        gap('spec','spec_gap','invalid acceptance specification: '+str(exc))
        spec = None
    for r in spec.requirements if spec is not None else []:
        if not r.applicable:
            continue
        definition = REGISTRY.get(r.check)
        if definition is None:
            gap(r.requirement_id,'spec_gap','unknown check: '+r.check)
            continue
        try:
            domain = spec.artifacts[r.location.artifact]
            if domain not in definition.domains:
                raise ValueError('registered check is not supported in '+domain)
            validate_location(r.location,domain)
            if r.location.region is not None and r.check not in {'visual','semantic'}:
                raise ValueError('region selector is unsupported by deterministic text/geometry checks')
            if any(getattr(r.location,field) is None or getattr(r.location,field)=='' for field in definition.required_location_fields):
                raise ValueError('missing required location fields: '+','.join(definition.required_location_fields))
            if r.location.cell and ':' in r.location.cell and r.check in {'excel.cell','excel.formula','excel.formula_exact','excel.formula_present','excel.cached_value','excel.recalculated_value','excel.number_format'}:
                raise ValueError('single-cell check cannot use a range')
            _expected(r.expected,definition.expected_schema)
            if r.check=='file.name' and any(v is not None for k,v in r.location.model_dump().items() if k!='artifact'):
                raise ValueError('filename check requires artifact scope')
            if r.check=='powerpoint.native_objects' and any(v is not None for k,v in r.location.model_dump().items() if k not in {'artifact','slide'}):
                raise ValueError('native object check supports whole deck or slide scope')
            if r.check in {'excel.formula','excel.formula_exact','excel.formula_present','excel.recalculated_value'}:
                from .formula_checks import validate_formula_options
                validate_formula_options(r)
            if r.check=='excel.range':
                from openpyxl.utils.cell import range_boundaries
                a,b,c,d=range_boundaries(r.location.cell)
                if len(r.expected)!=d-b+1 or len(r.expected[0])!=c-a+1:
                    raise ValueError('expected matrix dimensions differ from the declared range')
            if r.check=='facts.consistent':
                positions=r.options.get('locations')
                if not isinstance(positions,list) or not positions:
                    raise ValueError('fact locations must be nonempty')
                for position in positions:
                    loc=Location.model_validate(position)
                    if loc.artifact not in spec.artifacts:
                        raise ValueError('unknown fact artifact')
                    validate_location(loc,spec.artifacts[loc.artifact],fact=True)
            if r.check=='visual' and 'pages' in r.options:
                pages=r.options['pages']
                if not isinstance(pages,list) or not pages or any(type(p) is not int or p<1 for p in pages) or len(set(pages))!=len(pages):
                    raise ValueError('visual pages must be unique positive integer page numbers')
            if r.check=='preservation':
                from .preservation_checks import PreservationSpec
                policy=PreservationSpec.model_validate(r.options.get('preservation_spec'))
                source=r.options.get('source_path')
                if not isinstance(source,str) or spec.input_hashes.get(source)!=policy.source_hash:
                    raise ValueError('preservation source must be bound in frozen input_hashes')
        except (ValueError,TypeError,KeyError,IndexError) as exc:
            gap(r.requirement_id,'spec_gap',str(exc))
            continue
        missing=[name for name in definition.capabilities if not isinstance(capabilities,dict) or capabilities.get(name) is not True]
        if missing:
            gap(r.requirement_id,'assessment_gap','required capabilities unavailable: '+','.join(missing))
    status='SPEC_INCOMPLETE' if any(f.origin=='spec_gap' for f in findings) else 'ASSESSMENT_INCOMPLETE' if findings else 'PASS'
    return SpecAdmissionReport(status=status,requirement_coverage=RequirementCoverage(mandatory=0,covered=0,ratio=0),
        reasons=[f.message for f in findings],findings=findings)


def render_registry_markdown():
    lines=['# Registered artifact checks (T11)','',
        'Generated by `check_registry.render_registry_markdown()`; do not edit the table manually.','',
        'Preflight runs before artifact parsing. Unknown checks, invalid types/locations and unsupported legacy keys are `spec_gap`. Missing configured channels are `assessment_gap`. Neither is an artifact defect. Runtime channel failures remain visible; declared capability is not actual environment qualification. Nonapplicable checks retain their frozen reason.','',
        '| Check | Domains | Required location | Expected schema | Capabilities |',
        '|---|---|---|---|---|']
    for name,d in sorted(REGISTRY.items()):
        lines.append('| '+' | '.join([name,', '.join(d.domains),', '.join(d.required_location_fields) or 'optional scope',d.expected_schema,', '.join(d.capabilities) or 'parser'])+' |')
    lines+=['','Legacy adapters retain a record for every key: converted check IDs, explicit alias or unsupported reason. Requirements are never dropped because conversion failed. Known malformed specs are unavailable checks with failure_origin=spec_gap; checker exceptions remain assessment gaps.','',
        'Task requirement admission (T10) and check preflight are separate reports. A valid syntax registry does not establish reviewed task completeness. All evidence remains bound to evaluator source identity.','']
    return '\n'.join(lines)
