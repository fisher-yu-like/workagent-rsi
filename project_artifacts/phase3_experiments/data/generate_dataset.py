"""Generate the reproducible Phase 3 pilot task set.

The initial task set is project-generated. It is useful for pipeline
qualification, but it is not an external benchmark and must not be reported as
one.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = ROOT / "project_artifacts" / "phase3_experiments" / "data"
RAW_DIR = DATA_ROOT / "raw"
PROCESSED_DIR = DATA_ROOT / "processed"
SPLIT_DIR = DATA_ROOT / "splits"
PROTECTED_DIR = DATA_ROOT / "protected"
DATASET_VERSION = "synthetic-office-taskset-v0.1.0"
SEED = 20260923

DOMAINS = ("excel", "word", "powerpoint")
SPLITS = ("evolve", "develop", "regression", "hidden", "ood_transfer")
SPLIT_ASSIGNMENTS = (
    ("evolve", 12),
    ("develop", 6),
    ("regression", 4),
    ("hidden", 5),
    ("ood_transfer", 3),
)


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def task_for(index: int, split: str) -> dict:
    domain = DOMAINS[index % len(DOMAINS)]
    difficulty = ("easy", "medium", "hard")[index % 3]
    marker = f"P3-TASK-{index + 1:03d}"
    template_family = f"{domain}_generated_v1"
    return {
        "task_id": marker.lower(),
        "dataset_version": DATASET_VERSION,
        "domain": domain,
        "difficulty": difficulty,
        "split": split,
        "template_family": template_family,
        "instruction": (
            f"Produce a {domain} Office artifact for the {difficulty} pilot scenario "
            f"{index + 1:03d}. Preserve the exact marker {marker}."
        ),
        "input_files": [],
        "expected_constraints": {
            "required_text": marker,
            "output_format": domain,
            "marker": marker,
        },
        "risk_level": "medium" if difficulty == "hard" else "low",
        "hidden_test": split == "hidden",
        "source": {
            "kind": "project-generated",
            "source_ref": "project_artifacts/phase3_experiments/data/generate_dataset.py",
            "license": "Internal generated fixture; no external benchmark license claimed",
        },
        "seed": SEED,
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    for directory in (RAW_DIR, PROCESSED_DIR, SPLIT_DIR, PROTECTED_DIR):
        directory.mkdir(parents=True, exist_ok=True)
        for old_file in directory.glob("*.jsonl"):
            old_file.unlink()

    tasks: list[dict] = []
    index = 0
    for split, count in SPLIT_ASSIGNMENTS:
        for _ in range(count):
            tasks.append(task_for(index, split))
            index += 1

    write_jsonl(RAW_DIR / "tasks_all.jsonl", tasks)
    public_tasks = [task for task in tasks if not task["hidden_test"]]
    hidden_tasks = [task for task in tasks if task["hidden_test"]]
    write_jsonl(PROCESSED_DIR / "public_tasks.jsonl", public_tasks)
    write_jsonl(PROTECTED_DIR / "hidden_tasks.jsonl", hidden_tasks)
    for split in SPLITS:
        rows = [task for task in tasks if task["split"] == split]
        target = PROTECTED_DIR if split == "hidden" else SPLIT_DIR
        write_jsonl(target / f"{split}.jsonl", rows)

    file_paths = [
        RAW_DIR / "tasks_all.jsonl",
        PROCESSED_DIR / "public_tasks.jsonl",
        PROTECTED_DIR / "hidden_tasks.jsonl",
        PROTECTED_DIR / "hidden.jsonl",
        *sorted(SPLIT_DIR.glob("*.jsonl")),
    ]
    provenance = {
        "dataset_version": DATASET_VERSION,
        "generator": "generate_dataset.py",
        "seed": SEED,
        "task_count": len(tasks),
        "public_task_count": len(public_tasks),
        "protected_task_count": len(hidden_tasks),
        "split_counts": {split: sum(task["split"] == split for task in tasks) for split in SPLITS},
        "domain_counts": {domain: sum(task["domain"] == domain for task in tasks) for domain in DOMAINS},
        "source_kind": "project-generated",
        "license_note": "Internal generated fixture; no external benchmark license claimed",
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": {
            str(path.relative_to(DATA_ROOT)).replace("\\", "/"): sha256(path)
            for path in file_paths
        },
    }
    (DATA_ROOT / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(provenance, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
