"""Capture offline pytest evidence, including active expected-open regressions.

Usage: <explicit-python> run_hardening_checks.py T01 tests/test_review_regressions.py
An exit of 1 is preserved, never converted into a successful all-green claim.
"""

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
import uuid
import zipfile
import argparse
import re

REPO = next(path for path in Path(__file__).resolve().parents if (path / "pyproject.toml").is_file() and (path / "src").is_dir())
sys.path.insert(0, str(REPO / 'src'))
from workagent_rsi.environment_manifest import capture_environment

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('label', help='Evidence task/run label; letters, digits, hyphen or underscore')
PROFILES = {
    'benchmark-intake': ['tests/test_benchmark_corpus.py', 'tests/test_benchmark_scoring.py',
                         'tests/test_benchmark_review_run.py', 'tests/test_family_split_isolation.py',
                         'tests/test_external_dataset.py', 'tests/test_calibration_metrics.py',
                         'tests/test_human_label_provenance.py'],
    'calibration-human': ['tests/test_calibration_metrics.py', 'tests/test_human_label_provenance.py',
                           'tests/test_review_regressions.py', 'tests/test_family_split_isolation.py'],
    'calibration-splits': ['tests/test_calibration_case_integrity.py',
                           'tests/test_family_split_isolation.py', 'tests/test_external_dataset.py'],
    'full': [],
}
parser.add_argument('--profile', choices=sorted(PROFILES), help='Fixed task-focused selection, or the complete suite')
options, arguments = parser.parse_known_args()
if options.profile:
    if arguments:
        parser.error('--profile cannot be combined with custom pytest selectors or flags')
    arguments = PROFILES[options.profile]
label = options.label
if not re.fullmatch(r'[A-Za-z0-9_-]+', label):
    parser.error('label must use letters, digits, hyphen or underscore')
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
root = REPO / 'project_artifacts/results/hardening-v2' / label / stamp
root.mkdir(parents=True, exist_ok=False)
capture_environment(REPO, root / 'environment.json')
generated = REPO / '.pytest-tmp' / ('h-' + uuid.uuid4().hex[:8])
generated.parent.mkdir(parents=True, exist_ok=True)
command = [sys.executable, '-X', 'utf8', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '--basetemp=' + str(generated), '--junitxml=' + str(root / 'junit.xml'), *arguments]
source_paths = [p for directory in ['src', 'tests'] for p in (REPO / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
source_paths.append(REPO / 'pyproject.toml')
source_hashes = {p.relative_to(REPO).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source_paths)}
started = datetime.now(timezone.utc).isoformat()
with (root / 'stdout.txt').open('w', encoding='utf-8') as stdout, (root / 'stderr.txt').open('w', encoding='utf-8') as stderr:
    completed = subprocess.run(command, cwd=REPO, stdout=stdout, stderr=stderr, check=False)
ended = datetime.now(timezone.utc).isoformat()
cases = []
if (root / 'junit.xml').is_file():
    for case in ET.parse(root / 'junit.xml').iter('testcase'):
        failure = case.find('failure')
        error = case.find('error')
        skip = case.find('skipped')
        cases.append({'node': case.get('classname') + '::' + case.get('name'), 'status': 'failed' if failure is not None else 'error' if error is not None else 'skipped' if skip is not None else 'passed', 'detail': failure.get('message') if failure is not None else error.get('message') if error is not None else None})
with zipfile.ZipFile(root / 'generated.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(generated.rglob('*')):
        if path.is_file():
            archive.write(path, path.relative_to(generated).as_posix())
record = {'schema_version': 'hardening-run-evidence-v1', 'label': label, 'command': command, 'cwd': str(REPO), 'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(), 'started_at': started, 'ended_at': ended, 'exit_code': completed.returncode, 'cases': cases, 'source_hashes': source_hashes, 'generated_dir': str(generated), 'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file()}}
(root / 'run.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'evidence': str(root.relative_to(REPO)), 'exit_code': completed.returncode, 'counts': {s: sum(c['status'] == s for c in cases) for s in ['passed', 'failed', 'error', 'skipped']}}, ensure_ascii=False))
sys.exit(completed.returncode)
