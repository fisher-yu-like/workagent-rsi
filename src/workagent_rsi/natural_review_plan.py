"""Lossless compact cell observations and native OOXML warning evidence."""
import copy
import json
from pathlib import Path
import zipfile
from xml.etree import ElementTree as ET

from .hashing import sha256_file


def compact_observations(evidence):
    items=[i for p in evidence['partition']['partitions'] for i in p['items']]
    if Path(evidence['file']).suffix.lower()!='.xlsx':
        return {'kind':'ordered_text','items':[[{k:v for k,v in i['location'].items() if k!='artifact'},i['text']] for i in items]}
    cells={};other=[]
    for item in items:
        loc=item['location']
        if 'cell' in loc:
            key=json.dumps([loc['sheet'],loc['cell']],ensure_ascii=False,separators=(',',':'))
            if key in cells:raise ValueError('duplicate cell observation')
            cells[key]=item['text']
        else:other.append([{k:v for k,v in loc.items() if k!='artifact'},item['text']])
    return {'kind':'workbook_cells','cells':cells,'other':other}


def compact_output(output, baseline):
    """An explicit delta, never a filtered subset of task-relevant cells."""
    if output.get('kind')!='workbook_cells' or baseline.get('kind')!='workbook_cells':
        return output
    delta={'kind':'workbook_delta','baseline_source':'input-1',
           'changed_or_added':{k:v for k,v in output['cells'].items() if k not in baseline['cells'] or baseline['cells'][k]!=v},
           'removed':[k for k in baseline['cells'] if k not in output['cells']],
           'other':output['other'],
           'output_metadata':{k:v for k,v in output.items() if k not in {'kind','cells','other'}}}
    reconstructed={'kind':'workbook_cells','cells':copy.deepcopy(baseline['cells']),
                   'other':delta['other'],**delta['output_metadata']}
    for k in delta['removed']:reconstructed['cells'].pop(k)
    reconstructed['cells'].update(delta['changed_or_added']);reconstructed['other']=delta['other']
    if reconstructed!=output:raise ValueError('output delta is not lossless')
    return delta


def native_warning_parts(path):
    """Preserve omitted XML; no external links are followed or files saved."""
    path=Path(path);before=sha256_file(path);parts=[]
    with zipfile.ZipFile(path) as package:
        if sum(i.file_size for i in package.infolist())>256_000_000:raise ValueError('package expansion exceeds budget')
        for name in sorted(package.namelist()):
            if (name.startswith(('xl/charts/','xl/drawings/')) and name.endswith(('.xml','.rels'))):
                data=package.read(name).decode('utf-8')
                parts.append({'part':name,'xml':data})
            elif name.startswith('xl/worksheets/') and name.endswith('.xml'):
                root=ET.fromstring(package.read(name))
                for child in root:
                    if child.tag.rsplit('}',1)[-1] in {'extLst','dataValidations'}:
                        parts.append({'part':name,'xml':ET.tostring(child,encoding='unicode')})
    if sha256_file(path)!=before:raise ValueError('native source changed')
    return {'source_sha256':before,'parts':parts,
            'scope':'Raw chart/drawing/validation XML; embedded bitmap appearance and recalculation are not established.'}


def literal_observations(value):
    """Expose original strings verbatim so exact citations do not quote escapes."""
    lines=[]
    kind=value['kind']
    if kind=='workbook_delta':
        lines.append('ENTIRE OUTPUT copies all nonempty input-1 cells, then applies the following complete delta. This is not selected-cell evidence.')
        lines.append('REMOVED CELLS: '+json.dumps(value['removed'],ensure_ascii=False))
        cells=value['changed_or_added']
    elif kind=='workbook_cells':
        lines.append('ALL EXTRACTED NONEMPTY CELLS (formula strings are not recalculated results):')
        cells=value['cells']
    else:
        cells={}
    for key,text in cells.items():
        lines.extend(['CELL '+key,text,'END CELL'])
    entries=value.get('items',[]) if kind=='ordered_text' else value.get('other',[])
    for loc,text in entries:
        lines.extend(['LOCATION '+json.dumps(loc,ensure_ascii=False,separators=(',',':')),text,'END LOCATION'])
    if kind=='workbook_delta' and value.get('output_metadata'):
        raise ValueError('output metadata requires explicit literal rendering')
    return '\n'.join(lines)
