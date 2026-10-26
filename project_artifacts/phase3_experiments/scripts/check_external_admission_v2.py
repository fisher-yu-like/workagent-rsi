"""Check a frozen evaluator-side external admission report without model calls."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'src'))
from workagent_rsi.external_admission import validate_external_admission

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--root',type=Path)
    args=parser.parse_args()
    report=validate_external_admission(json.loads(args.manifest.read_text(encoding='utf-8')),args.root or args.manifest.parent)
    print(json.dumps(report,indent=2))
    return 0 if report['formal_ready'] else 2

if __name__=='__main__':raise SystemExit(main())
