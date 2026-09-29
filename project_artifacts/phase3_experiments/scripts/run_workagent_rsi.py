"""Freeze a project-generated Office RSI invocation; run only after qualified baseline."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from workagent_rsi.candidate_provider import WorkAgentCandidateProvider
from workagent_rsi.contracts import TaskSpec
from workagent_rsi.evaluator import OfficeArtifactEvaluator
from workagent_rsi.hashing import canonical_json_hash, sha256_file
from workagent_rsi.workagent_experiment import WorkAgentExperimentRunner
from workagent_rsi.workagent_provider import WorkAgentConfig, WorkAgentSkill

from docx import Document
from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Inches


RESULT_ROOT = ROOT / "project_artifacts/results/qualification/general-office"
CONFIG = ROOT / "project_artifacts/phase3_experiments/configs/general_office_rsi.json"
BASELINE = RESULT_ROOT / "20260929T195704Z-a4674234"
PILOT_CONFIG = ROOT / "project_artifacts/phase3_experiments/configs/general_office_pilot.json"
SCHEMA = ROOT / "project_artifacts/phase3_experiments/provider/candidate_patch.schema.json"
SKILL = WorkAgentSkill(instructions=(
    "Complete the Office task by creating or editing the requested real file. "
    "Use the staged input copy only. Write the final file inside outputs/, reopen it "
    "with the corresponding Python Office library, and list it in deliverables.json. "
    "Do not report completion until the file and manifest exist."
))
PROVIDER = WorkAgentConfig()
THRESHOLDS = {"develop_gain": 0.05, "regression_tolerance": 0.01,
              "hidden_degradation": 0.01, "ood_degradation": 0.01, "max_cost_delta": 1.0}
IDS = {f"{domain}-{kind}" for domain in ("excel", "word", "powerpoint") for kind in ("create", "edit")}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _source_inputs(root: Path) -> dict[str, str]:
    inputs = root / "inputs"
    inputs.mkdir()
    book = Workbook()
    sheet = book.active
    sheet.title = "Transactions"
    for row in (("Item", "Revenue"), ("Alpha", 40), ("Beta", 55), ("Gamma", 65)):
        sheet.append(row)
    book.save(inputs / "transactions.xlsx")
    doc = Document()
    doc.add_heading("Draft Status", level=1)
    doc.add_paragraph("The pilot completed on 12 September.")
    doc.add_paragraph("This draft needs a final structure and an action item.")
    doc.save(inputs / "status_draft.docx")
    deck = Presentation()
    for label in ("Baseline: two regions", "Rollout options"):
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(1)).text = label
    deck.save(inputs / "briefing_draft.pptx")
    return {path.name: sha256_file(path) for path in inputs.iterdir()}


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing or unsafe evidence: {path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid evidence: {path.name}")
    return value


def validate_baseline(root: Path) -> tuple[dict, list[str]]:
    """Fail closed on missing or contradictory six-task qualification evidence."""
    summary = _read_json(root / "summary.json")
    if summary.get("pilot_id") != "general-office-six-task-engineering-pilot-v1":
        raise ValueError("baseline pilot identity mismatch")
    if Path(summary.get("invocation", "")).resolve() != root.resolve():
        raise ValueError("baseline invocation path mismatch")
    if summary.get("config_sha256") != sha256_file(root / "config.json") or summary["config_sha256"] != sha256_file(PILOT_CONFIG):
        raise ValueError("baseline task config hash mismatch")
    if summary.get("evaluator_source_sha256") != OfficeArtifactEvaluator.evaluator_hash():
        raise ValueError("baseline evaluator hash mismatch")
    rows = summary.get("rows")
    if not isinstance(rows, list) or len(rows) != 6 or {row.get("task_id") for row in rows if isinstance(row, dict)} != IDS:
        raise ValueError("baseline must have exactly six distinct task rows")
    if summary.get("task_count") != 6 or summary.get("success_count") != sum(r["state"] == "SUCCEEDED" for r in rows) or summary.get("failure_count") != sum(r["state"] == "FAILED" for r in rows):
        raise ValueError("baseline row counts contradict summary")
    source_hashes = summary.get("source_hashes")
    if not isinstance(source_hashes, dict) or set(source_hashes) != {"transactions.xlsx", "status_draft.docx", "briefing_draft.pptx"}:
        raise ValueError("baseline source input hash records incomplete")
    provenance = _read_json(root / "input_provenance.json")
    if provenance.get("sha256") != source_hashes or provenance.get("provenance") != "project-generated":
        raise ValueError("baseline input provenance mismatch")
    for name, digest in source_hashes.items():
        if not isinstance(digest, str) or not SHA256.fullmatch(digest) or sha256_file(root / "inputs" / name) != digest:
            raise ValueError(f"baseline source input hash mismatch: {name}")
    gaps = []
    for row in rows:
        task_id = row["task_id"]
        domain, kind = task_id.split("-")
        task_root = root / task_id
        if row.get("domain") != domain or row.get("kind") != kind or row.get("state") not in ("SUCCEEDED", "FAILED"):
            raise ValueError(f"baseline task identity or terminal state invalid: {task_id}")
        if _read_json(task_root / "qualification_result.json") != row:
            raise ValueError(f"baseline persisted row mismatch: {task_id}")
        result = _read_json(task_root / "result.json")
        com = _read_json(task_root / "com_reopen.json")
        if result.get("state") not in ("SUCCEEDED", "FAILED") or row.get("harness_state") != result["state"]:
            raise ValueError(f"baseline harness evidence mismatch: {task_id}")
        input_names = {"excel": ["transactions.xlsx"], "word": ["status_draft.docx"], "powerpoint": ["briefing_draft.pptx"]}[domain] if kind == "edit" else []
        expected = {name: source_hashes[name] for name in input_names}
        if row.get("source_hashes_before") != expected or row.get("source_hashes_after") != expected or row.get("input_hashes_ok") is not True:
            raise ValueError(f"baseline row input hashes invalid: {task_id}")
        if row["state"] == "SUCCEEDED":
            evaluation = _read_json(task_root / "evaluation.json")
            artifacts = result.get("artifacts", [])
            if row.get("evaluation_passed") is not True or evaluation.get("passed") is not True or row.get("com_ok") is not True or com.get("ok") is not True or not row.get("suffix_ok") or len(artifacts) != 1 or len(row.get("artifact_sha256", [])) != 1:
                raise ValueError(f"baseline success lacks evaluator/artifact/COM evidence: {task_id}")
            artifact = Path(artifacts[0]["path"])
            if not artifact.is_file() or sha256_file(artifact) != artifacts[0].get("sha256") or row["artifact_sha256"][0] != artifacts[0]["sha256"]:
                raise ValueError(f"baseline artifact hash invalid: {task_id}")
        else:
            gaps.append(task_id)
    return summary, gaps


def run_invocation(baseline_root: Path, output_root: Path, *, runner_factory=WorkAgentExperimentRunner) -> int:
    """Persist immutable preflight evidence before any model or candidate process."""
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc)
    config_bytes = CONFIG.read_bytes()
    config = json.loads(config_bytes)
    splits = config["splits"]
    if set(splits) != {"develop", "regression", "hidden", "ood_transfer"} or sum(map(len, splits.values())) != 12:
        raise ValueError("RSI task matrix must contain four splits and twelve tasks")
    tasks = {split: [TaskSpec.model_validate(row) for row in rows] for split, rows in splits.items()}
    (root / "rsi_tasks.json").write_bytes(config_bytes)
    source_hashes = _source_inputs(root)
    split_hashes = {split: canonical_json_hash([task.model_dump(mode="json") for task in rows]) for split, rows in tasks.items()}
    contract = {
        "experiment_id": config["experiment_id"], "provenance": "project-generated", "seed": config["seed"],
        "task_config_sha256": sha256_file(root / "rsi_tasks.json"), "split_hashes": split_hashes,
        "source_input_hashes": source_hashes, "evaluator_sha256": OfficeArtifactEvaluator.evaluator_hash(),
        "baseline_skill_sha256": canonical_json_hash(SKILL.model_dump()),
        "provider": "codex-cli/ollama", "model_identity": f"ollama:{PROVIDER.model}",
        "workagent_executable": PROVIDER.executable, "workagent_timeout_seconds": PROVIDER.timeout_seconds,
        "candidate_timeout_seconds": 180, "promotion_thresholds": THRESHOLDS,
        "baseline_invocation": str(Path(baseline_root).resolve()),
        "baseline_summary_sha256": sha256_file(Path(baseline_root) / "summary.json"),
    }
    _write_json(root / "contract.json", contract)
    _write_json(root / "baseline_skill.json", SKILL.model_dump())
    reason = None
    baseline = None
    try:
        baseline, gaps = validate_baseline(Path(baseline_root))
        if gaps:
            reason = f"六任务基线缺少各格式成功的创建与编辑；失败任务：{', '.join(gaps)}"
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        reason = f"baseline evidence invalid: {exc}"
    summary = {
        "status": "blocked" if reason else "running", "block_reason": reason,
        "baseline": {"invocation": str(Path(baseline_root).resolve()),
                     "success_count": baseline.get("success_count") if baseline else None,
                     "failure_count": baseline.get("failure_count") if baseline else None,
                     "task_count": baseline.get("task_count") if baseline else None},
        "rsi_started": False, "candidate_started": False, "token_usage": "unavailable",
        "started_at": started.isoformat(), "ended_at": datetime.now(timezone.utc).isoformat(),
        "wall_time_seconds": (datetime.now(timezone.utc) - started).total_seconds(),
    }
    if reason is None:
        runner = runner_factory(workagent_config=PROVIDER, input_base=root / "inputs")
        provider = WorkAgentCandidateProvider(SCHEMA, "local-1", executable=PROVIDER.executable,
            timeout_seconds=180, model_identity=f"ollama:{PROVIDER.model}",
            extra_args=["--ignore-user-config", "--oss", "--local-provider", "ollama", "--model", PROVIDER.model])
        summary["rsi_started"] = True
        summary["rsi_result"] = runner.run(tasks, SKILL, provider, root / "rsi", rounds=1)
        summary["status"] = summary["rsi_result"].get("status", "completed")
    _write_json(root / "summary.json", summary)
    analysis = {"status": summary["status"], "block_reason": reason, "baseline": summary["baseline"],
                "rsi_started": summary["rsi_started"], "claims_allowed": False,
                "external_benchmark": False, "unavailable_is_not_score": True, "token_usage": "unavailable"}
    _write_json(root / "analysis.json", analysis)
    report = ["# 通用 Office WorkAgent RSI 资格报告", "", "本次仅使用项目生成的输入，不是外部 benchmark。", "",
              f"基线：`{baseline_root}`", f"RSI invocation：`{root}`", "",
              f"状态：{'阻断' if reason else summary['status']}",
              f"基线：{summary['baseline']['success_count']}/6 成功；失败 {summary['baseline']['failure_count']}/6。",
              f"原因：{reason or '资格门禁通过，已运行一轮 RSI。'}", "",
              "未把失败或不可用任务转换为分数；未声明外部 benchmark 成绩。", ""]
    (root / "qualification_report.md").write_text("\n".join(report), encoding="utf-8")
    summary["disk_bytes"] = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
    _write_json(root / "summary.json", summary)
    return 1 if reason else 0


def main() -> int:
    invocation = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    root = RESULT_ROOT / invocation
    result = run_invocation(BASELINE, root)
    print(json.dumps({"invocation": str(root), "status": "blocked" if result else "completed"}))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
