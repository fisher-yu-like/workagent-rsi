"""Read-only evidence preparation for mixed public Office task inputs.

Partitions preserve extracted content. They do not prove native-object coverage,
recalculation, cross-partition consistency or complete task acceptance.
"""
import json
from pathlib import Path
import warnings
import zipfile

from .assessment_contracts import Location, Requirement
from .evidence_partition import EvidenceBudget, partition_evidence
from .hashing import sha256_file
from .semantic_assessment import extract_evidence
from .view_safety import ordinary_file


def prepare_file_evidence(path, artifact, *, max_bytes=32_000_000,
                          max_chars=2_000_000, max_items=40_000):
    path=ordinary_file(Path(path))
    before=sha256_file(path)
    if path.stat().st_size>max_bytes:
        raise ValueError('input exceeds fixed file byte budget')
    suffix=path.suffix.lower()
    notices=[]
    if suffix in {'.txt','.md','.json'}:
        text=path.read_text(encoding='utf-8-sig')
        if suffix=='.json':json.loads(text)
        if len(text)>max_chars:
            raise ValueError('text exceeds fixed character budget')
        # Keep exact source slices, including whitespace and original JSON keys.
        items=[{'evidence_id':f'{artifact}-text-{offset}',
                'location':{'artifact':artifact},'text':text[offset:offset+40_000],
                'source_span':[offset,min(offset+40_000,len(text))]}
               for offset in range(0,len(text),40_000)]
        evidence={'items':items,'limitations':['Text evidence only; no visual or native Office coverage.']}
    elif suffix in {'.xlsx','.docx','.pptx'}:
        with zipfile.ZipFile(path) as package:
            infos=package.infolist()
            if len(infos)>10_000 or sum(i.file_size for i in infos)>256_000_000:
                raise ValueError('Office package exceeds fixed expansion budget')
        obj=None
        with warnings.catch_warnings(record=True) as observed:
            warnings.simplefilter('always')
            try:
                if suffix=='.xlsx':
                    from openpyxl import load_workbook
                    obj=load_workbook(path,data_only=False)
                elif suffix=='.docx':
                    from docx import Document
                    obj=Document(path)
                else:
                    from pptx import Presentation
                    obj=Presentation(path)
                evidence=extract_evidence(obj,artifact,max_chars=max_chars,max_items=max_items)
            finally:
                if obj is not None and hasattr(obj,'close'):obj.close()
            notices=[str(w.message) for w in observed]
    else:
        raise ValueError('unsupported public evidence format: '+suffix)
    requirement=Requirement(requirement_id='extraction-scope',description='Extracted public file content',
        check='semantic',location=Location(artifact=artifact),dimension='content',
        evidence_source='Exact task-authorized public input or output')
    partition=partition_evidence(evidence['items'],requirement,EvidenceBudget())
    if sha256_file(path)!=before:
        raise ValueError('public evidence file changed during preparation')
    return {'artifact':artifact,'file':str(path),'sha256':before,
            'scope':'Extracted text/data only; not whole task acceptance',
            'limits':{'file_bytes':max_bytes,'extracted_chars':max_chars,'extracted_items':max_items},
            'extracted_items':len(evidence['items']),'limitations':evidence['limitations'],
            'parser_warnings':notices,'native_coverage_qualified':False,
            'text_partition_complete':partition.complete,
            'partition':partition.model_dump(mode='json')}
