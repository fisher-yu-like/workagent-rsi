"""Attach hash-bound cached actual pages to a new opaque human review pack.

No server or model call is made. The twelve standards reuse their existing
renderings; new natural output render attempts are already counted separately.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from workagent_rsi.hashing import canonical_json_hash, sha256_file
from workagent_rsi.view_safety import ordinary_file, relative_reference


def attach(output: Path, standards_pack: Path, natural_cache: Path) -> dict:
    public = output / 'blind-review-pack'
    manifest = json.loads((public / 'review-manifest.json').read_text(encoding='utf-8'))
    previous = json.loads((standards_pack / 'review-manifest.json').read_text(encoding='utf-8'))
    old_cases = {r['case_id']: r for r in previous['cases']}
    cache = {}
    for row in json.loads((standards_pack / 'rendered-pages.json').read_text(encoding='utf-8')):
        source = old_cases[row['case_id']]
        if sha256_file(ordinary_file(standards_pack / relative_reference(source['artifact']))) != source['artifact_hash']:
            raise ValueError('previous standard artifact changed')
        cache[source['artifact_hash']] = {**row, 'reused_standard': True,
            'pages': [{**p, 'source_path': str(standards_pack / relative_reference(p['file']))} for p in row['pages']]}
    for row in json.loads((natural_cache / 'render-results.json').read_text(encoding='utf-8')):
        result = row.get('render', {})
        if result and result.get('artifact_sha256') != row['artifact_sha256']:
            raise ValueError('natural rendering source binding mismatch')
        cache[row['artifact_sha256']] = {'status': row['status'], 'error': result.get('error', row.get('error')),
            'renderer_identity': result.get('renderer_identity'), 'environment': result.get('environment', {}),
            'reused_standard': False, 'pages': [{**p, 'source_path': p['path']} for p in result.get('pages', [])]}
    page = (public / 'index.html').read_text(encoding='utf-8')
    records = []
    for row in manifest['cases']:
        artifact = ordinary_file(public / relative_reference(row['artifact']))
        if sha256_file(artifact) != row['artifact_hash']:
            raise ValueError('review artifact changed')
        saved = cache.get(row['artifact_hash'], {'status': 'unavailable', 'error': 'No actual cached render', 'pages': []})
        images = []
        if saved['status'] == 'available':
            for number, item in enumerate(saved['pages'], 1):
                if item['page'] != number:
                    raise ValueError('cached page coverage is not contiguous')
                source = ordinary_file(Path(item['source_path']))
                if sha256_file(source) != item['sha256']:
                    raise ValueError('cached actual page changed')
                name = f'{row["case_id"]}-page-{number}.png'
                shutil.copyfile(source, public / name)
                images.append({'file': name, 'sha256': item['sha256'], 'page': number})
        start = page.index(f'<article id="{row["case_id"]}">')
        end = page.index('</article>', start)
        section = page[start:end]
        content = ''.join(f'<img loading="lazy" src="{p["file"]}" alt="实际渲染第{p["page"]}页">' for p in images)
        if not images:
            content = '<p>实际渲染未覆盖该成品，请打开原文件核对；证据不足时可选择 INCOMPLETE。</p>'
        if '<div class="pages"></div>' not in section:
            raise ValueError('review pages were already attached')
        page = page[:start] + section.replace('<div class="pages"></div>', '<div class="pages">' + content + '</div>') + page[end:]
        records.append({'case_id': row['case_id'], 'status': saved['status'], 'error': saved.get('error'),
            'pages': images, 'renderer_identity': saved.get('renderer_identity'),
            'environment': saved.get('environment', {}), 'reused_standard': saved.get('reused_standard', False)})
    (public / 'index.html').write_text(page, encoding='utf-8')
    (public / 'rendered-pages.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report_path = output / 'agreement-report.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    report.update(rendered_cases=sum(r['status'] == 'available' for r in records),
        rendered_pages=sum(len(r['pages']) for r in records),
        standards_renders_reused=sum(r['reused_standard'] for r in records),
        rendering_gaps=sum(r['status'] != 'available' for r in records),
        new_model_calls=0, new_server_operations=0,
        blind_pack_hash=canonical_json_hash({p.name: sha256_file(p) for p in public.iterdir() if p.is_file()}))
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--standards-pack', type=Path, required=True)
    parser.add_argument('--natural-cache', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(attach(args.output, args.standards_pack, args.natural_cache), ensure_ascii=False))
