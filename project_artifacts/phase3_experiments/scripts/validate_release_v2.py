"""Validate separate engineering, live, research and external evidence levels."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'src'))
from workagent_rsi.release_validation import validate_release

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    report=validate_release(args.manifest)
    if args.output:
        with args.output.open('x',encoding='utf-8') as handle:json.dump(report,handle,indent=2)
    print(json.dumps(report,indent=2))
    return 0 if report['engineering_pass'] else 2

if __name__=='__main__':raise SystemExit(main())
