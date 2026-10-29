import io
import tarfile

import pytest

from workagent_rsi.benchmark_supplement import (
    balanced_candidate_cohort, parse_word_definitions, source_figure_bytes, render_frozen_reference,
)


def task(name, domain, digest, *, family=None, split='develop'):
    return {'base_task_id': name, 'domain': domain, 'source_family': family or name,
            'benchmark': 'test', 'instruction': 'Public task.', 'split': split,
            'variants': [{'variant_id': name + '/one', 'inputs': [
                {'path': name + '.bin', 'sha256': digest}]}]}


def test_word_definitions_are_data_and_template_expressions_are_refused():
    source = '''export const TEST_CASES: TestCase[] = [
  {
    name: "Quoted case",
    file: "memo.docx",
    instruction: `Keep "quotes".\nChange the heading.`,
    expectPresent: ["PRIVATE_EXPECTATION"],
    expectAbsent: [],
    suite: "features",
  },
];'''
    rows = parse_word_definitions(source)
    assert rows[0]['instruction'] == 'Keep "quotes".\nChange the heading.'
    assert rows[0]['expectPresent'] == ['PRIVATE_EXPECTATION']
    with pytest.raises(ValueError, match='expression'):
        parse_word_definitions(source.replace('Change the heading.', '${dangerous()}'))


def test_balance_excludes_calibration_and_transitively_related_sources():
    rows = [task('reserved', 'word', 'a' * 64, split='human_calibration'),
            task('linked', 'word', 'a' * 64, family='shared'),
            task('transitive', 'word', 'b' * 64, family='shared')]
    rows += [task(f'{d}{i}', d, f'{i + n * 10:064x}')
             for n, d in enumerate(('excel', 'word', 'powerpoint'), 1) for i in range(4)]
    selected, report = balanced_candidate_cohort(rows, per_domain=3, seed=7)
    assert report['per_domain_base_tasks'] == {'excel': 3, 'word': 3, 'powerpoint': 3}
    assert report['max_domain_count_ratio'] == 1.0
    assert report['final_test_count'] == 0
    assert report['excluded_calibration_related_tasks'] == 3
    assert not {'reserved', 'linked', 'transitive'} & {r['base_task_id'] for r in selected}
    assert all(len(r['variants']) == 1 for r in selected)
    again, _ = balanced_candidate_cohort(list(reversed(rows)), per_domain=3, seed=7)
    assert selected == again


def test_shortage_is_explicit_and_not_filled_by_another_task_in_same_family():
    rows = [task(f'{d}{i}', d, f'{i + n * 10:064x}', family=d)
            for n, d in enumerate(('excel', 'word', 'powerpoint'), 1) for i in range(3)]
    with pytest.raises(ValueError, match='independent'):
        balanced_candidate_cohort(rows, per_domain=2, seed=1)


def test_selected_archive_payload_is_hash_bound_and_never_extracts_other_paths(tmp_path):
    import hashlib
    archive = tmp_path / 'paper.tar'
    with tarfile.open(archive, 'w') as tar:
        for name, body in [('figure.pdf', b'public figure'), ('../outside.py', b'bad')]:
            info = tarfile.TarInfo(name)
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
    digest = hashlib.sha256(b'public figure').hexdigest()
    assert source_figure_bytes(archive, 'figure.pdf', digest) == b'public figure'
    assert not (tmp_path.parent / 'outside.py').exists()
    with pytest.raises(ValueError, match='hash'):
        source_figure_bytes(archive, 'figure.pdf', '0' * 64)
    with pytest.raises(ValueError, match='unsafe'):
        source_figure_bytes(archive, '../outside.py', digest)


def test_frozen_reference_uses_upstream_alpha_compositing_and_dimension_hash(tmp_path):
    import pymupdf
    document = pymupdf.open()
    page = document.new_page(width=1, height=1)
    page.draw_rect(page.rect, fill=(1, 0, 0), color=None)
    pdf = tmp_path / 'figure.pdf'
    document.save(pdf)
    document.close()
    spec = {'maximum_scale': 1, 'maximum_side': 1,
            'pixel_sha256': '4f6d2b5e0b69dbcb09517d911a392f1dfb58a3f88c84d322cacd658b2c1c52ba'}
    assert render_frozen_reference(pdf, spec, tmp_path / 'reference.png') == spec['pixel_sha256']
    spec['pixel_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='pixels'):
        render_frozen_reference(pdf, spec, tmp_path / 'bad.png')
    assert not (tmp_path / 'bad.png').exists()
