# WorkAgent-RSI 代码包

日常代码只需要理解两个入口：

```python
from workagent_rsi import Harness

result = Harness().run(task)
```

如果要直接使用数据结构，可以从 `workagent_rsi.data` 导入 `Task`、`Change`、`Report` 和 `Version`。

## 代码分组

- `harness.py`：总入口；把一次任务放入一个结果目录。
- `run.py`：执行任务，支持 smoke 和真实 Office 文件生成。
- `learn.py`：从失败记录中诊断问题并提出受限修改。
- `check.py`：组织验证、文件评估和晋级判断。
- `store.py`：统一管理文件、日志、技能版本和回滚。
- `data.py`：给现有 Pydantic 契约提供短名称。

这些短名称是完整能力的入口，而不是另一套缩水实现：`Learn.export()`、`Learn.diagnose()` 和 `Learn.propose()` 对应候选隔离与生成；`Check.verify()`、`Check.evaluate()`、`Check.evaluate_split()` 和 `Check.promote()` 对应验证、评估和晋级；`Store` 提供 artifact、trace、版本 lineage、champion 与 rollback 的委托方法；`Harness.resume()` 用于读取已落盘运行。底层长模块仍保留，以保证闭环实验和兼容导入不受影响。

候选隔离、泄漏检查、冻结评估、注册表和实验 runner 仍由原有内部模块实现。它们没有被删除，也没有把不同权限合并到同一个对象中。短名称只负责降低理解成本，完整功能继续可用。

## 运行目录

默认结果目录是 `project_artifacts/results/<run-id>/`。一个目录内包含任务、最终 JSON、SQLite trace、生成文件、内容寻址 artifact 和技能记录，便于查看和归档。

## WorkAgent 与 Office 评估

普通入口仍然是 `Harness.run(task)`。Office 任务默认使用 WorkAgent 生成文件；非 Office smoke 任务继续使用轻量 evaluator。可通过 `execution_provider` 显式选择 `workagent`、`local_office`、`com` 或 `libreoffice`。

Office 成品共用远端 `SharedAssessment`，随后由 `ArtifactEvaluator` 评分、`ArtifactVerifier` 定位问题。结果目录中的 `assessment/` 保存 `assessment.json`、`score.json`、`issues.json` 和可读的 `report.md`；`result.json` 的 evaluation 字段包含身份和报告路径。兼容分数 `evaluation.score` 为 0–1，原始总分保存在 `score.json` 的 0–100 `total_score` 中。未完成的必需检查会得到 `score: null` 和 `UNAVAILABLE` 状态。

默认验收规格由 `expected_constraints` 转换，只检查其中声明的确定性要求。需要语义或视觉检查时，将完整 `acceptance_spec` 放在 `expected_constraints.acceptance_spec`，为每个评分维度声明权重和明确标准，并通过模型配置启用相应通道：

```python
from workagent_rsi import Harness

task = {
    "task_id": "quarterly-summary",
    "domain": "excel",
    "instruction": "Create the requested quarterly summary workbook.",
    "expected_constraints": {
        "acceptance_spec": {
            "task_id": "quarterly-summary",
            "version": "v1",
            "artifacts": {"output": "excel"},
            "requirements": [
                {
                    "requirement_id": "formula-total",
                    "description": "The total cell uses the required formula.",
                    "check": "excel.formula",
                    "location": {"artifact": "output", "sheet": "Summary", "cell": "B4"},
                    "expected": "=SUM(B2:B3)",
                    "critical": True,
                    "dimension": "correctness",
                    "evidence_source": "task specification",
                }
            ],
            "dimension_weights": {"correctness": 1.0},
        }
    },
}

result = Harness().run(task)
```

Semantic and visual requirements use `check: "semantic"` or `check: "visual"` and must state the criterion in the requirement. Enable the matching channel with a `ModelReviewConfig`, for example `Harness(model_review_config={"provider": "api", "model": "<model-name>", "semantic_enabled": True, "visual_enabled": True})`; the API key is read from the configured environment variable and is not written to run records. The CLI accepts the same JSON through `--model-review-config`. If a required model or render channel is unavailable, assessment remains incomplete.

For one output, the sole `AcceptanceSpec.artifacts` key maps to that output. For multiple outputs, each key must exactly equal one WorkAgent deliverable path such as `outputs/summary.xlsx`; every generated output must be declared. Missing, duplicate, or extra mappings produce an incomplete assessment rather than an arbitrary file choice.
