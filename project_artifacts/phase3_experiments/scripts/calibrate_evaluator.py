"""Run the production deterministic checks on the frozen development corpus."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from workagent_rsi.calibration_data import load_calibration_cases
from workagent_rsi.calibration_metrics import calibrate
from workagent_rsi.environment_manifest import capture_environment
from workagent_rsi.hashing import sha256_file


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    start=datetime.now(timezone.utc).isoformat()
    cases=load_calibration_cases(args.manifest)
    report=calibrate(cases,{'corpus_root':str(args.manifest.parent)},args.output)
    capture_environment(ROOT,args.output/'environment.json')
    code=1 if report['known_critical_false_accepts'] or report['permitted_equivalent_false_rejects'] else 0
    stdout=json.dumps(report,sort_keys=True)
    (args.output/'stdout.txt').write_text(stdout+'\n',encoding='utf-8')
    (args.output/'stderr.txt').write_text('',encoding='utf-8')
    record={'command':[sys.executable,*sys.argv],'cwd':str(ROOT),'started_at':start,
        'ended_at':datetime.now(timezone.utc).isoformat(),'exit_code':code,
        'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'input_manifest_sha256':sha256_file(args.manifest),
        'files':{p.name:sha256_file(p) for p in args.output.iterdir() if p.is_file()}}
    (args.output/'run.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(stdout)
    return code


if __name__=='__main__': raise SystemExit(main())
