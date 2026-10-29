"""Bounded, read-only Word checks beyond python-docx body extraction.

These checks establish only explicit predicates. They do not certify that an
agreement is legally correct or that all unrelated content was preserved.
"""
from pathlib import Path
import re
from zipfile import ZipFile

from lxml import etree

from .hashing import sha256_file
from .view_safety import ordinary_file

W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS={'w':W}
SCOPES={'all','body','headers','footers','footnotes','comments'}


def validate_word_rules(rules):
    fields={
        'text':{'kind','scope','text','count'},
        'replace':{'kind','scope','before','after','preserve_bold'},
        'comments':{'kind','author','text','count','min_count'},
        'table_row':{'kind','cells','after_row','table_contains'},
        'blank_paragraphs':{'kind'},'tracked_clean':{'kind'},
        'ordered_text':{'kind','scope','texts'},
        'comments_preserved':{'kind','remove_ids'},
        'footnote_suffix':{'kind','note_id','suffix'},
        'tables_equal':{'kind','tables'},
        'paragraphs_equal':{'kind','parts'},
    }
    if not isinstance(rules,list) or not 1<=len(rules)<=256:raise ValueError('Word rules must be a bounded nonempty list')
    for r in rules:
        if not isinstance(r,dict) or r.get('kind') not in fields or set(r)-fields[r['kind']]:raise ValueError('unknown Word rule or fields')
        if r.get('scope','all') not in SCOPES:raise ValueError('unsupported Word scope')
        kind=r['kind']
        for key in ({'text':['text'],'replace':['before','after'],'comments':['author']}.get(kind,[])):
            if not isinstance(r.get(key),str) or not r[key]:raise ValueError('nonempty '+key+' required')
        if 'count' in r and (type(r['count']) is not int or r['count']<0):raise ValueError('count must be a nonnegative integer')
        if 'min_count' in r and (type(r['min_count']) is not int or r['min_count']<1 or 'count' in r):raise ValueError('min_count must be positive and distinct from count')
        if 'preserve_bold' in r and type(r['preserve_bold']) is not bool:raise ValueError('preserve_bold must be boolean')
        if 'text' in r and (not isinstance(r['text'],str) or not r['text']):raise ValueError('text must be nonempty')
        if 'after_row' in r and (not isinstance(r['after_row'],str) or not r['after_row']):raise ValueError('after_row must be nonempty')
        if 'table_contains' in r and (not isinstance(r['table_contains'],str) or not r['table_contains']):raise ValueError('table_contains must be nonempty')
        if kind in {'table_row','ordered_text'}:
            key='cells' if kind=='table_row' else 'texts'
            if not isinstance(r.get(key),list) or not r[key] or any(not isinstance(v,str) or not v for v in r[key]):raise ValueError('explicit nonempty '+key+' required')
        if kind=='comments_preserved' and (not isinstance(r.get('remove_ids'),list) or any(not isinstance(i,str) or not i.isdigit() for i in r['remove_ids'])):raise ValueError('explicit comment IDs required')
        if kind=='footnote_suffix' and (not isinstance(r.get('note_id'),str) or not r['note_id'].isdigit() or not isinstance(r.get('suffix'),str) or not r['suffix']):raise ValueError('explicit footnote and suffix required')
        if kind=='tables_equal' and (not isinstance(r.get('tables'),list) or not r['tables'] or any(not isinstance(t,list) or any(not isinstance(row,list) or any(not isinstance(c,str) for c in row) for row in t) for t in r['tables'])):raise ValueError('explicit table matrices required')
        if kind=='paragraphs_equal' and (not isinstance(r.get('parts'),dict) or not r['parts'] or any(not isinstance(k,str) or not re.fullmatch(r'word/(?:document|header\d+|footer\d+|footnotes)\.xml',k) or not isinstance(v,list) or any(not isinstance(t,str) for t in v) for k,v in r['parts'].items())):raise ValueError('explicit paragraph part inventory required')
    return rules


def _package(path):
    path=ordinary_file(path)
    with ZipFile(path) as z:
        infos=z.infolist()
        if len(infos)>10000 or len({i.filename for i in infos})!=len(infos) or sum(i.file_size for i in infos)>100_000_000:raise ValueError('Word package size/identity budget exceeded')
        parser=etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False)
        parts={}
        for name in z.namelist():
            if name=='word/document.xml' or re.fullmatch(r'word/(?:header\d+|footer\d+|footnotes|comments)\.xml',name):
                raw=z.read(name)
                if b'<!DOCTYPE' in raw or b'<!ENTITY' in raw:raise ValueError('Word DTD/entity declarations are not supported')
                parts[name]=etree.fromstring(raw,parser)
    if 'word/document.xml' not in parts:raise ValueError('Word document body missing')
    return parts


def _selected(parts,scope):
    def match(name):
        return scope=='all' or scope=='body' and name=='word/document.xml' or scope=='headers' and '/header' in name or scope=='footers' and '/footer' in name or scope=='footnotes' and name=='word/footnotes.xml' or scope=='comments' and name=='word/comments.xml'
    return {name:xml for name,xml in parts.items() if match(name)}


def _paragraphs(parts,scope='all'):
    return [(name,p) for name,xml in _selected(parts,scope).items() for p in xml.xpath('.//w:p',namespaces=NS)]


def _text(node):
    return ''.join(node.xpath('.//w:t/text()',namespaces=NS))


def _bold_states(parts,scope,text):
    states=[]
    for _,p in _paragraphs(parts,scope):
        chars=[];flags=[]
        for run in p.xpath('.//w:r',namespaces=NS):
            value=_text(run);bold=run.find('w:rPr/w:b',NS)
            is_bold=None if bold is None else bold.get('{'+W+'}val','true') not in {'0','false','off'}
            chars.append(value);flags.extend([is_bold]*len(value))
        joined=''.join(chars)
        for match in re.finditer(re.escape(text),joined):
            selected=flags[match.start():match.end()]
            states.append(True if all(v is True for v in selected) else False if all(v is False for v in selected) else None)
    return states


def inspect_word_rules(output,rules,source=None):
    validate_word_rules(rules)
    output=ordinary_file(output);source=ordinary_file(source) if source else None
    hashes={str(p):sha256_file(p) for p in [output,source] if p is not None}
    actual=_package(output);before=_package(source) if source else None
    rows=[]
    for rule in rules:
        kind=rule['kind'];scope=rule.get('scope','all');passed=False;detail={}
        paragraphs=[_text(p) for _,p in _paragraphs(actual,scope)]
        if kind=='text':
            count=sum(p.count(rule['text']) for p in paragraphs)
            passed=count==rule['count'] if 'count' in rule else count>0
            detail={'occurrences':count}
        elif kind=='replace':
            if before is None:raise ValueError('replacement requires frozen source')
            old,new=rule['before'],rule['after']
            source_parts=_selected(before,scope);output_parts=_selected(actual,scope)
            bindings=[]
            for name,node in source_parts.items():
                old_count=sum(_text(p).count(old) for p in node.xpath('.//w:p',namespaces=NS))
                if not old_count:continue
                orig_new=sum(_text(p).count(new) for p in node.xpath('.//w:p',namespaces=NS))
                target=output_parts.get(name)
                texts=[_text(p) for p in target.xpath('.//w:p',namespaces=NS)] if target is not None else []
                ok=bool(texts) and sum(t.count(old) for t in texts)==0 and sum(t.count(new) for t in texts)==old_count+orig_new
                uncertain=False
                if ok and rule.get('preserve_bold'):
                    original_styles=_bold_states({name:node},scope,old)
                    target_styles=_bold_states({name:target},scope,new)
                    # Effective inherited styles and mixed occurrence mapping
                    # need a richer style resolver;counts cannot prove location.
                    uncertain=orig_new>0 or None in original_styles or len(set(original_styles))>1
                    if not uncertain and any(original_styles):
                        ok=False not in target_styles
                        uncertain=None in target_styles
                bindings.append({'part':name,'source_occurrences':old_count,'passed':ok,'style_uncertain':uncertain})
            # A source with no such term is an unresolved rule, not a successful edit.
            if not bindings:
                rows.append({'rule':rule,'status':'NEEDS_REVIEW','observed':'replacement term absent from source'});continue
            passed=all(b['passed'] for b in bindings) and not any(old in p for p in paragraphs)
            if passed and any(b['style_uncertain'] for b in bindings):
                rows.append({'rule':rule,'status':'NEEDS_REVIEW','observed':{'parts':bindings,'reason':'inherited or mixed-position bold cannot be established from explicit run properties'}});continue
            detail={'parts':bindings}
        elif kind=='comments':
            root=actual.get('word/comments.xml');comments=root.findall('w:comment',NS) if root is not None else []
            body=actual['word/document.xml']
            starts=set(body.xpath('.//w:commentRangeStart/@w:id',namespaces=NS));ends=set(body.xpath('.//w:commentRangeEnd/@w:id',namespaces=NS));refs=set(body.xpath('.//w:commentReference/@w:id',namespaces=NS))
            selected=[c for c in comments if c.get('{'+W+'}author')==rule['author'] and ('text' not in rule or rule['text'] in _text(c))]
            anchored=all(c.get('{'+W+'}id') in starts&ends&refs for c in selected)
            passed=anchored and (len(selected)==rule['count'] if 'count' in rule else len(selected)>=rule.get('min_count',1))
            detail={'matched_comments':len(selected),'anchored':anchored}
        elif kind=='table_row':
            matches=[]
            for table in actual['word/document.xml'].xpath('.//w:tbl',namespaces=NS):
                values=[[_text(c) for c in row.findall('w:tc',NS)] for row in table.findall('w:tr',NS)]
                if 'table_contains' in rule and not any(rule['table_contains'] in row for row in values):continue
                matches.extend(i for i,row in enumerate(values) if row==rule['cells'] and ('after_row' not in rule or i>0 and rule['after_row'] in values[i-1]))
            passed=len(matches)==1;detail={'matching_rows':len(matches)}
        elif kind=='blank_paragraphs':
            if before is None:raise ValueError('blank-line preservation requires source')
            old=[i for i,(_,p) in enumerate(_paragraphs(before,'body')) if not _text(p).strip()];new=[i for i,(_,p) in enumerate(_paragraphs(actual,'body')) if not _text(p).strip()]
            passed=old==new;detail={'source_blank_paragraphs':old,'output_blank_paragraphs':new}
        elif kind=='tables_equal':
            tables=[[[_text(c) for c in row.findall('w:tc',NS)] for row in t.findall('w:tr',NS)] for t in actual['word/document.xml'].xpath('.//w:tbl',namespaces=NS)]
            passed=tables==rule['tables'];detail={'actual_tables':tables}
        elif kind=='paragraphs_equal':
            matched={name:[_text(p) for p in actual[name].xpath('.//w:p',namespaces=NS)] if name in actual else None for name in rule['parts']}
            passed=matched==rule['parts'];detail={'matching_parts':[name for name in matched if matched[name]==rule['parts'][name]]}
        elif kind=='footnote_suffix':
            if before is None:raise ValueError('footnote suffix requires frozen source')
            def notes(parts):
                root=parts.get('word/footnotes.xml')
                return {n.get('{'+W+'}id'):_text(n) for n in root.findall('w:footnote',NS)} if root is not None else {}
            orig,updated=notes(before),notes(actual);key=rule['note_id']
            passed=key in orig and updated.get(key)==orig[key]+rule['suffix'];detail={'note_id':key}
        elif kind=='comments_preserved':
            if before is None:raise ValueError('comment preservation requires frozen source')
            def inventory(parts):
                root=parts.get('word/comments.xml')
                return {n.get('{'+W+'}id'):(n.get('{'+W+'}author'),_text(n)) for n in root.findall('w:comment',NS)} if root is not None else {}
            orig=inventory(before);updated=inventory(actual);removed=set(rule['remove_ids'])
            markers={name:set(actual['word/document.xml'].xpath('.//w:'+name+'/@w:id',namespaces=NS)) for name in ('commentRangeStart','commentRangeEnd','commentReference')}
            kept=set(orig)-removed
            passed=removed<=set(orig) and updated=={k:v for k,v in orig.items() if k not in removed} and all(not removed&ids and kept<=ids for ids in markers.values())
            detail={'removed_ids':sorted(removed),'remaining_ids':sorted(updated)}
        elif kind=='tracked_clean':
            markers=sum(len(x.xpath('.//w:ins|.//w:del|.//w:moveFrom|.//w:moveTo',namespaces=NS)) for x in actual.values())
            passed=markers==0 and not any(token in p for p in paragraphs for token in ('{+','+}','[-','-]'))
            detail={'revision_elements':markers}
        elif kind=='ordered_text':
            text='\n'.join(paragraphs);cursor=0;passed=True
            for value in rule['texts']:
                at=text.find(value,cursor)
                if at<0:passed=False;break
                cursor=at+len(value)
        rows.append({'rule':rule,'status':'PASS' if passed else 'FAIL','observed':detail})
    if any(sha256_file(Path(p))!=digest for p,digest in hashes.items()):raise ValueError('Word input changed during inspection')
    status='FAIL' if any(r['status']=='FAIL' for r in rows) else 'NEEDS_REVIEW' if any(r['status']=='NEEDS_REVIEW' for r in rows) else 'PASS'
    return status,0 if status=='FAIL' else None if status=='NEEDS_REVIEW' else 1,{'rules':rows,'input_hashes':hashes}
