"""Rerun the Word and PowerPoint qualification cases after the local skill repair."""

from __future__ import annotations

import json
from pathlib import Path

from workagent_rsi.harness import Harness
from run_local_three_domain_qualification import RESULT_ROOT, ROUNDS, build_task


def main() -> None:
    rerun_root = RESULT_ROOT / "rerun-after-prompt-repair"
    rerun_root.mkdir(exist_ok=False)
    rows = []
    for round_name, marker, records in ROUNDS:
        source = RESULT_ROOT / "inputs" / f"{round_name}.json"
        assert json.loads(source.read_text(encoding="utf-8")) == records
        for domain in ("word", "powerpoint"):
            task = build_task(round_name, marker, domain, source)
            result = Harness(rerun_root, execution_provider="local_office").run(task)
            assessment_root = Path(result["result_dir"]) / "assessment"
            score = json.loads((assessment_root / "score.json").read_text(encoding="utf-8"))
            issues = json.loads((assessment_root / "issues.json").read_text(encoding="utf-8"))
            rows.append({
                "round": round_name,
                "domain": domain,
                "state": result["state"],
                "acceptance": score["acceptance_status"],
                "score": score["total_score"],
                "issues": len(issues["issues"]),
                "result_dir": result["result_dir"],
            })
    (rerun_root / "summary.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
