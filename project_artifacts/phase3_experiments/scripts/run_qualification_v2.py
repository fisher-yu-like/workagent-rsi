"""T31 qualification entrypoint. Live calls are disabled in the shipped config."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'src'))
from workagent_rsi.study_entrypoint import main
if __name__=='__main__':raise SystemExit(main('qualification'))
