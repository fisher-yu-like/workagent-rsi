"""Build the development-only 90-case authored Office calibration corpus."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from workagent_rsi.calibration_data import build_calibration_cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cases = build_calibration_cases(args.output, ROOT / 'tests/fixtures/calibration/case_manifest.json')
    print(json.dumps({'count': len(cases), 'manifest': str(args.output / 'case_manifest.json'),
                      'source_kind': 'project-generated', 'model_calls': 0}))


if __name__ == '__main__':
    main()
