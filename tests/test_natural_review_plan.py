import json
import zipfile

from workagent_rsi.natural_review_plan import compact_observations,compact_output,native_warning_parts,literal_observations
from workagent_rsi.hashing import sha256_file


def test_delta_keeps_unchanged_baseline_and_added_changed_removed_cells():
    old={'kind':'workbook_cells','cells':{'A1':'1','A2':'=A1','A3':'remove'},'other':[]}
    new={'kind':'workbook_cells','cells':{'A1':'1','A2':'=A1*2','A4':'new'},'other':[['title','Sheet']]}
    delta=compact_output(new,old)
    assert delta['changed_or_added']=={'A2':'=A1*2','A4':'new'} and delta['removed']==['A3']
    assert delta['baseline_source']=='input-1' and old['cells']['A2']=='=A1'


def test_text_compaction_preserves_order_and_exact_content():
    evidence={'file':'output.docx','partition':{'partitions':[{'items':[
        {'location':{'artifact':'output','paragraph':1},'text':'First'},
        {'location':{'artifact':'output','paragraph':2},'text':'Second'}]}]}}
    result=compact_observations(evidence)
    assert result['items']==[[{'paragraph':1},'First'],[{'paragraph':2},'Second']]


def test_input_parser_warning_metadata_is_not_inherited_by_output():
    old={'kind':'workbook_cells','cells':{'A1':'1'},'other':[],
         'native_warning_xml':{'parts':['source-only validation']}}
    new={'kind':'workbook_cells','cells':{'A1':'1'},'other':[]}
    delta=compact_output(new,old)
    assert delta['output_metadata']=={} and delta['changed_or_added']=={}


def test_formula_and_text_quotes_remain_exact_citable_source_substrings():
    formula='=IFERROR(A1/B1,"NA")'
    data={'kind':'workbook_cells','cells':{'["Ledger","B6"]':formula},'other':[]}
    text=literal_observations(data)
    assert formula in text and '\\"NA\\"' not in text
    prose='The customer said "preserve this".\nNext line.'
    assert prose in literal_observations({'kind':'ordered_text','items':[[{'paragraph':1},prose]]})


def test_native_parts_preserve_omitted_chart_and_extended_validation_without_mutation(tmp_path):
    p=tmp_path/'input.xlsx'
    with zipfile.ZipFile(p,'w') as z:
        z.writestr('xl/charts/chart1.xml','<chart><externalData id="missing"/></chart>')
        z.writestr('xl/drawings/drawing1.xml','<drawing><shape>Important</shape></drawing>')
        z.writestr('xl/worksheets/sheet1.xml','<worksheet><extLst><validation>Allowed</validation></extLst><sheetData/></worksheet>')
    before=sha256_file(p);result=native_warning_parts(p)
    assert len(result['parts'])==3
    assert 'Important' in json.dumps(result) and 'Allowed' in json.dumps(result)
    assert result['source_sha256']==before==sha256_file(p)
