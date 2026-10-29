# WorkAgent-RSI 代码包

当前评估协议见 [LLM 任务评估说明](../../docs/operations/llm-task-review.md)。旧实验的恢复记录见[历史交接说明](../../docs/operations/evaluation-rsi-v2.md)；真实模型调用默认关闭。

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

普通入口仍是 `Harness.run(task)`。Office 任务默认由 WorkAgent 生成文件，
也可按现有执行配置选择其他执行器。所有产物评估都经过 `SharedAssessment`：
原任务、原始输入、成品文本与结构观测，以及可用的实际渲染页发给同一个 LLM。

```python
from workagent_rsi import Harness

task = {
    "task_id": "quarterly-summary",
    "domain": "excel",
    "instruction": "Summarize the quarterly sales from the supplied workbook.",
    "input_files": ["source.xlsx"],
}
harness = Harness(model_review_config={
    "provider": "api",
    "model": "<approved-model-name>",
    "retries": 0,
})
# Run only after the actual execution/model configuration and budget are approved.
result = harness.run(task)
```

模型返回任务是否明确可行、PASS/PARTIAL/FAIL/NEEDS_REVIEW、完成度、理由和问题。
代码保留这些判断，只为兼容报告把 0–1 分数换算为 0–100；不会按权重、关键项
阈值或隐藏答案重新判分。`expected_constraints` 可保留在历史任务中，但不再
编译成验收规则，也不会当作隐藏答案传给 judge。旧 `AcceptanceSpec` 输入不用于新评估。

默认 `provider` 为 `disabled`；没有 judge 或调用失败时，评估不完整、质量分为 null。
API 凭据从配置指定的环境变量读取。实际视觉判断还需要独立配置的 Office worker；
缺少渲染、上下文超限或图片超限必须留下限制记录，不能静默截断或用规则替代。

每次运行的 `assessment/` 目录保存 `assessment.json`、`score.json`、`issues.json`
和 `report.md`。报告以 `llm-task-review-v1` 标识新语义。原始模型回复、调用用量、
来源哈希和错误记录由模型传输层保存。归档产物引用保留原文件名。

内循环使用模型问题修复产物，保持 skill 冻结；外循环修改 skill 后重新执行任务，
比较同一模型协议给出的结果。模型提示、配置和评估器身份在比较期间保持冻结。
详见[协议与限制](../../docs/operations/llm-task-review.md)。
