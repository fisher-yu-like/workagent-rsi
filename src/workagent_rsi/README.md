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
