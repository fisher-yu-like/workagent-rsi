import json
from workagent_rsi.contracts import TaskSpec


def sales_task(root, task_id="sales", records=None, hidden=False):
    root.mkdir(parents=True, exist_ok=True)
    source = root / f"{task_id}.json"
    source.write_text(
        json.dumps(
            records
            or [
                {"region": "East", "amount": 10},
                {"region": "West", "amount": 20},
                {"region": "East", "amount": 5},
            ]
        ),
        encoding="utf-8",
    )
    return TaskSpec(
        task_id=task_id,
        domain="excel",
        instruction="Summarize all input sales by region with a chart and two-decimal totals.",
        input_files=(str(source),),
        expected_constraints={"sales_summary": True},
        hidden_test=hidden,
    )
