from pathlib import Path

from workagent_rsi.cli import main


def test_cli_runs_smoke_task_and_writes_json(tmp_path: Path):
    task = tmp_path / "task.yaml"
    task.write_text(
        "task_id: cli-smoke\n"
        "domain: smoke\n"
        "instruction: hello\n"
        "expected_constraints:\n"
        "  required_text: hello\n",
        encoding="utf-8",
    )
    output = tmp_path / "run.json"
    code = main([str(task), "--output", str(output)])
    assert code == 0
    assert output.exists()
    assert '"state": "SUCCEEDED"' in output.read_text(encoding="utf-8")

