"""Validate Phase 3 task-set structure, splits, provenance and leakage boundaries."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = ROOT / "project_artifacts" / "phase3_experiments" / "data"
RAW = DATA_ROOT / "raw" / "tasks_all.jsonl"
PUBLIC = DATA_ROOT / "processed" / "public_tasks.jsonl"
HIDDEN = DATA_ROOT / "protected" / "hidden_tasks.jsonl"
PROVENANCE = DATA_ROOT / "provenance.json"
REPORT = DATA_ROOT / "quality_report.json"
EXPECTED_SPLITS = {"evolve": 12, "develop": 6, "regression": 4, "hidden": 5, "ood_transfer": 3}
EXPECTED_DOMAINS = {"excel": 10, "word": 10, "powerpoint": 10}


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"blank line in {path} at {line_number}")
            rows.append(json.loads(line))
    return rows


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    checks: list[dict] = []
    failures: list[str] = []
    all_tasks = load_jsonl(RAW)
    public_tasks = load_jsonl(PUBLIC)
    hidden_tasks = load_jsonl(HIDDEN)

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            failures.append(f"{name}: {detail}")

    ids = [task.get("task_id") for task in all_tasks]
    instructions = [task.get("instruction") for task in all_tasks]
    check("task_count", len(all_tasks) == 30, f"count={len(all_tasks)} expected=30")
    check("unique_task_ids", len(ids) == len(set(ids)), f"unique={len(set(ids))} total={len(ids)}")
    check("unique_instructions", len(instructions) == len(set(instructions)), f"unique={len(set(instructions))} total={len(instructions)}")
    check("split_counts", Counter(task.get("split") for task in all_tasks) == EXPECTED_SPLITS, str(Counter(task.get("split") for task in all_tasks)))
    check("domain_counts", Counter(task.get("domain") for task in all_tasks) == EXPECTED_DOMAINS, str(Counter(task.get("domain") for task in all_tasks)))
    check("public_excludes_hidden", all(not task["hidden_test"] for task in public_tasks), f"hidden_in_public={sum(task['hidden_test'] for task in public_tasks)}")
    check("protected_matches_hidden", {task["task_id"] for task in hidden_tasks} == {task["task_id"] for task in all_tasks if task["hidden_test"]}, f"protected={len(hidden_tasks)} expected={sum(task['hidden_test'] for task in all_tasks)}")
    check("public_count", len(public_tasks) == 25, f"count={len(public_tasks)} expected=25")
    check("hidden_count", len(hidden_tasks) == 5, f"count={len(hidden_tasks)} expected=5")

    required = {"task_id", "dataset_version", "domain", "difficulty", "split", "template_family", "instruction", "expected_constraints", "source", "seed"}
    malformed = [task.get("task_id") for task in all_tasks if not required.issubset(task) or task.get("expected_constraints", {}).get("required_text") not in task.get("instruction", "")]
    check("schema_fields", not malformed, f"malformed_tasks={malformed}")
    source_kinds = {task.get("source", {}).get("kind") for task in all_tasks}
    check("source_boundary", source_kinds == {"project-generated"}, str(source_kinds))
    versions = {task.get("dataset_version") for task in all_tasks}
    check("version_consistency", len(versions) == 1, f"versions={sorted(versions)}")
    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8")) if PROVENANCE.exists() else {}
    check("provenance_version", provenance.get("dataset_version") == (all_tasks[0].get("dataset_version") if all_tasks else None), f"provenance={provenance.get('dataset_version')}")
    check("provenance_count", provenance.get("task_count") == len(all_tasks), f"provenance={provenance.get('task_count')} actual={len(all_tasks)}")

    manifest = {
        "status": "pass" if not failures else "fail",
        "dataset_version": all_tasks[0].get("dataset_version") if all_tasks else None,
        "task_count": len(all_tasks),
        "public_count": len(public_tasks),
        "protected_count": len(hidden_tasks),
        "split_counts": dict(Counter(task.get("split") for task in all_tasks)),
        "domain_counts": dict(Counter(task.get("domain") for task in all_tasks)),
        "checks": checks,
        "failures": failures,
        "files": {str(path.relative_to(DATA_ROOT)).replace("\\", "/"): file_hash(path) for path in (RAW, PUBLIC, HIDDEN)},
    }
    REPORT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
