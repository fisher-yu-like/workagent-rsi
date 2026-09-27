# WorkAgent-RSI 项目介绍

## 先用一句话说明

这个项目让一个办公助手完成任务、检查生成的文件，并把确认有效的工作方法保存下来，供下一次任务继续使用。

目前支持 Excel、Word 和 PowerPoint 文件。生成的文件是真实的 `.xlsx`、`.docx` 和 `.pptx`，可以用对应的 Office 库重新打开检查。

## 你只需要记住五个词

```text
Harness  总入口
Run      完成一次任务并生成文件
Learn    根据失败记录提出改进
Check    检查文件和改进是否安全、有效
Store    保存文件、日志、版本和回滚记录
```

日常使用只需要调用 `Harness`：

```python
from workagent_rsi import Harness

result = Harness("project_artifacts/results").run({
    "task_id": "report-001",
    "domain": "word",
    "instruction": "Create a document containing REPORT-001",
    "expected_constraints": {"required_text": "REPORT-001"},
})
print(result["state"])
print(result["result_path"])
```

命令行也可以完成同一件事：

```powershell
py -3.12 -m workagent_rsi.cli examples/smoke_task.yaml
```

每次运行都会在下面创建一个独立目录：

```text
project_artifacts/results/<run-id>/
├── task.json       # 本次任务
├── result.json     # 最终结果
├── trace.db        # 运行过程和状态变化
├── artifacts/      # 内容寻址保存的文件
├── generated/      # 本次生成的 Office 文件
└── skills/         # 本次运行需要的技能版本记录
```

## 一次正常运行怎么走

```text
任务
  ↓
Run 生成文件
  ↓
Check 重新打开文件并检查格式和要求
  ↓
Store 保存结果
  ↓
返回 SUCCEEDED 或 FAILED
```

默认的 Office 运行直接使用任务中写明的 `required_text`。因此普通单轮运行从正常路径开始，不需要先制造一个错误再观察改进。

如果需要研究技能改进，才会额外进入下面的流程：

```text
失败记录 → Learn 提出小修改 → Check 验证 → Check 评估 → 接受或拒绝 → Store 保存版本
```

这部分仍然保留完整能力：候选在隔离目录中生成，不能读取 hidden 数据，也不能修改 evaluator、晋级规则、工具白名单或历史证据；验证、评估、晋级和回滚仍由不同的内部对象负责。对外名称变短，安全边界没有变弱。

## 当前代码怎么对应

| 简单名称 | 入口文件 | 作用 |
|---|---|---|
| `Harness` | `src/workagent_rsi/harness.py` | 对外唯一的日常入口 |
| `Run` | `src/workagent_rsi/run.py` | 选择 smoke 或 Office 运行器并完成一次任务 |
| `Learn` | `src/workagent_rsi/learn.py` | 诊断失败并生成受限候选 |
| `Check` | `src/workagent_rsi/check.py` | 提供验证、评估和晋级服务 |
| `Store` | `src/workagent_rsi/store.py` | 统一保存文件、日志、技能版本和回滚信息 |
| `Task`、`Change`、`Report` | `src/workagent_rsi/data.py` | 提供容易理解的数据名称 |

原来的 `candidate_provider.py`、`verifier.py`、`frozen_evaluator.py`、`registry.py` 等文件继续保留，作为内部实现和兼容导入。这样已有测试、实验记录和外部调用不会因为改名失效；新代码可以只使用上表中的短名称。

简化入口不是功能删减：`Learn` 仍然提供候选工作区导出、失败诊断和候选生成；`Check` 仍然提供补丁验证、Office 文件评估、冻结 split 评估和晋级门禁；`Store` 仍然提供内容寻址 artifact、trace、版本注册、lineage、champion 切换和回滚；`Harness.resume()` 可以读取已有运行的状态和事件。更复杂的 E01-E12 runner 和完整 `RSILoop` 仍保留在内部模块中，原有导入和实验脚本继续有效。

## 两篇参考工作的影响

项目借鉴了两类思想：

1. RRSI 提醒我们，候选修改要小、要有证据，并且要经过独立检查，不能只看开发集分数。
2. RSI 框架工作提醒我们，真正的持续改进必须把有效修改保存到下一轮，而不是只在当前任务里反思一次。

因此项目保留了候选隔离、泄漏检查、冻结评估、回归和 OOD 检查、成本门禁、版本注册及回滚。当前实现属于 L1 和受控 L2：系统能自动执行规定的改进流程，也能在批准范围内选择修改类型；不会把当前结果表述成 L3、L4 或 L5。

## 结果和历史证据

所有新运行结果统一放在 `project_artifacts/results/`。其中：

- `project_artifacts/results/<run-id>/`：日常单轮运行；
- `project_artifacts/results/qualification/`：新的本地资格运行；
- `project_artifacts/results/experiments/`：新的研究实验运行。

旧的 `project_artifacts/phase1_harness/results/` 和 `project_artifacts/phase3_experiments/results/` 是此前已经完成的历史证据，保留用于追溯，不会被新运行覆盖。

历史 E01-E12 pilot 使用了一个专门的缺陷基线来验证闭环机制。那是研究用历史记录，不是普通运行的默认行为，也不代表外部 WorkAgent 的性能。当前 pilot 只有 30 个项目生成任务，不能作为正式主研究结论。

## 常用命令

```powershell
# 安装
py -3.12 -m pip install -e .

# 运行全部测试
py -3.12 -m pytest -q --basetemp="$env:TEMP\workagent-rsi-tests"

# 运行一次普通任务，结果写入 project_artifacts/results
py -3.12 -m workagent_rsi.cli examples/smoke_task.yaml

# 运行本地资格检查，结果也写入 project_artifacts/results
py -3.12 project_artifacts/phase3_experiments/scripts/run_b0_office_qualification.py
```

## 研究资料

- 两篇参考工作的调研：[docs/literature_review.md](literature_review.md)
- Agent 执行规则：[Agent.md](../Agent.md)
- 三阶段执行计划：[Codex三阶段项目执行计划.md](../Codex三阶段项目执行计划.md)
- 当前代码包说明：[src/workagent_rsi/README.md](../src/workagent_rsi/README.md)
