# Codex 三阶段项目执行计划

你是本项目的技术负责人兼执行工程师。请直接在当前工作目录中检查、设计、实现、运行和验证项目，而不是只提供建议。

## 一、总目标

项目分为三个阶段：

1. 设计并跑通 Harness + WorkAgent Pipeline，交付真实运行结果；
2. 设计 RSI 整体框架和训练计划；
3. 获取或构建数据集，开始执行训练与评估实验，并记录真实分数。

必须严格执行阶段门禁：当前阶段未完成且未经我确认，不得进入下一阶段。

## 二、执行原则

1. 开始前先检查：
   - 当前目录及代码仓库结构；
   - README、AGENTS.md、配置文件和已有文档；
   - Harness、WorkAgent、RSI 相关代码；
   - 当前 Git 状态；
   - 已有脚本、测试、数据和运行环境。

2. 不覆盖或删除用户已有修改，不执行破坏性 Git 操作。

3. 优先基于现有代码工作，不无必要地重写项目。

4. 不得虚构：
   - Pipeline 已经跑通；
   - WorkAgent 运行结果；
   - 数据集来源；
   - 实验日志；
   - 模型分数；
   - 截图或验证结果。

5. 明确区分：
   - 设计方案；
   - 已实现功能；
   - 实际运行结果；
   - 尚未验证的假设；
   - 当前阻塞项。

6. 每次运行都必须记录：
   - 执行命令；
   - 工作目录；
   - 代码版本或 Git commit；
   - 环境和依赖版本；
   - 配置参数；
   - 开始及结束时间；
   - 标准输出和错误输出；
   - 退出码；
   - 生成的文件；
   - 实际评估结果。

7. 遇到普通问题时自行诊断和修复，不要因为小问题中断工作。只有在缺少无法推断的关键业务信息、凭据、权限或外部资源时才向我提问。

8. 如果需要联网、安装依赖或访问外部服务，应按照当前环境的权限机制申请执行，不得绕过权限限制。

9. PPT、Word 和 Excel 必须是可以正常打开的真实文件：
   - PPT：`.pptx`
   - Word：`.docx`
   - Excel：`.xlsx`

   不得仅将 Markdown 或文本文件修改扩展名冒充 Office 文件。

10. 所有核心结果应同时保留 Markdown、JSON、CSV 等便于复查和版本管理的格式。

## 三、统一目录

如果仓库中没有既定目录规范，则创建：

```text
project_artifacts/
├── execution_plan.md
├── artifact_manifest.md
├── phase1_harness/
│   ├── design/
│   ├── implementation/
│   ├── configs/
│   ├── scripts/
│   ├── logs/
│   ├── results/
│   └── reports/
├── phase2_rsi/
│   ├── design/
│   ├── training_plan/
│   └── reports/
└── phase3_experiments/
    ├── datasets/
    ├── configs/
    ├── scripts/
    ├── logs/
    ├── checkpoints/
    ├── results/
    └── reports/
```

如果项目已有更合理的目录结构，可以复用，但必须在 `artifact_manifest.md` 中列出所有交付物的实际路径。

## 四、计划管理

首先创建或更新：

`project_artifacts/execution_plan.md`

至少包含：

- 阶段；
- 任务；
- 状态：pending / in_progress / completed / blocked；
- 验收条件；
- 依赖项；
- 输出文件；
- 实际结果；
- 阻塞原因。

任何时候只能有一个主要任务处于 `in_progress` 状态。完成任务后及时更新状态，不要等到最后一次性填写。

---

# 第一阶段：Harness 设计与 Pipeline 跑通

第一阶段分为两个门禁步骤。

## Phase 1A：Harness 详细设计

### 任务1：仓库与环境审计

检查并记录：

1. 仓库目录结构；
2. 现有 Harness 和 WorkAgent 代码位置；
3. 当前启动方式；
4. 依赖和运行环境；
5. 已有测试；
6. 已有输入输出格式；
7. 外部服务依赖；
8. 缺失功能；
9. 当前 Pipeline 可能的阻塞点；
10. Harness、WorkAgent、RSI 在当前项目中的实际含义。

输出：

- `project_artifacts/phase1_harness/design/repository_audit.md`
- `project_artifacts/phase1_harness/design/environment_inventory.md`

如果代码库中无法确定某个术语的含义，列出你的工作假设，不要自行伪造已有实现。

### 任务2：设计 Harness 总体架构

逐个组件给出：

1. 名称和职责；
2. 输入、输出和数据结构；
3. 接口定义；
4. 依赖关系；
5. 调用顺序；
6. 状态生命周期；
7. 配置项及默认值；
8. 日志和可观测性；
9. 异常处理；
10. 重试、超时和取消机制；
11. 幂等性和断点恢复；
12. 资源隔离和并发控制；
13. 安全边界；
14. 测试方法；
15. 验收标准；
16. 后续扩展方式。

设计至少覆盖：

- 任务输入与校验；
- 任务编排器；
- WorkAgent 适配层；
- 工具调用层；
- 环境或 Sandbox 管理；
- 状态管理；
- Artifact 管理；
- 日志与 Trace；
- 超时、重试和取消；
- 结果验证器；
- 评分或评估模块；
- 报告生成模块。

### 任务3：设计完整 Pipeline

给出：

- 端到端执行流程；
- 状态机；
- 正常路径；
- 失败路径；
- 重试路径；
- 中断恢复路径；
- 输入输出契约；
- 最小可运行样例；
- 单元测试、集成测试和端到端测试方案。

输出：

- `harness_architecture.md`
- `component_specifications.md`
- `pipeline_design.md`
- `interfaces.md`
- `test_and_acceptance_plan.md`
- Mermaid 架构图、流程图和时序图
- `implementation_backlog.md`

### Phase 1A 验收条件

必须满足：

- 每个 Harness 组件均有明确职责和接口；
- Pipeline 输入、输出和失败行为明确；
- WorkAgent 接入方式明确；
- 实施任务可直接执行；
- 测试及验收标准可量化；
- 风险和假设已经列出；
- 没有将设计内容描述成已实现结果。

完成 Phase 1A 后：

1. 更新 `execution_plan.md`；
2. 输出设计文件清单；
3. 总结核心设计、假设和风险；
4. 停止执行；
5. 等待我批准后再进入 Phase 1B。

不要在未经批准时提前实现或运行 Pipeline。

---

## Phase 1B：实现并跑通 Pipeline

只有我批准 Phase 1A 后才能执行。

### 任务1：实现 Harness

按照已批准设计：

1. 补齐或修改代码；
2. 创建配置文件；
3. 创建启动脚本；
4. 添加必要测试；
5. 保持与现有项目兼容；
6. 对偏离设计的地方记录原因。

### 任务2：测试

依次执行：

1. 静态检查；
2. 单元测试；
3. 组件集成测试；
4. 最小冒烟测试；
5. 完整端到端测试。

必须保留原始输出、错误日志和退出码。

### 任务3：运行真实 WorkAgent Pipeline

至少执行：

- 一个最小任务；
- 一个完整任务；
- 一个可控失败任务，用于验证错误处理或恢复机制。

每次运行记录：

- Run ID；
- 输入；
- 配置；
- WorkAgent 实际执行轨迹；
- 工具调用；
- 中间状态；
- 日志；
- Artifact；
- 最终输出；
- 验证结果；
- 耗时；
- 是否成功；
- 失败原因。

真实运行记录写入：

- `phase1_harness/logs/`
- `phase1_harness/results/`
- `phase1_harness/reports/run_report.md`
- `phase1_harness/results/run_summary.csv`
- `phase1_harness/results/run_summary.json`

如果 Pipeline 没有跑通：

1. 不得伪造成功；
2. 定位根因；
3. 尝试修复；
4. 重新运行；
5. 保留失败和修复过程；
6. 如最终仍失败，明确标记为 blocked。

### 任务4：生成第一阶段 Office 交付物

生成：

- `Harness与WorkAgent运行报告.pptx`
- `Harness详细设计与运行报告.docx`
- `Harness运行数据.xlsx`

Excel 至少包含以下工作表：

- Run Summary；
- Task Details；
- Timing；
- Errors；
- Metrics；
- Environment；
- Artifact Index。

PPT 至少包含：

- 目标；
- 系统架构；
- Harness 组件；
- Pipeline 流程；
- WorkAgent 执行过程；
- 真实运行结果；
- 错误与修复；
- 指标；
- 风险；
- 下一步。

Word 至少包含：

- 设计说明；
- 安装部署；
- 配置说明；
- 使用方法；
- 测试方法；
- 运行记录；
- 问题分析；
- 复现说明。

生成后验证文件确实存在、非空且能够被对应库成功读取。

### Phase 1B 验收条件

- Pipeline 实际运行；
- WorkAgent 产生真实结果；
- 运行命令可复现；
- 测试结果和日志齐全；
- PPT、Word、Excel 均为有效文件；
- 所有成功与失败结果均有证据；
- Artifact 清单完整。

完成后停止，等待我确认是否进入第二阶段。

---

# 第二阶段：RSI 整体框架与训练计划

只有第一阶段通过验收后才能执行。

## 任务1：定义 RSI

优先从现有代码和文档确定 RSI 的含义、目标和边界。

记录：

- RSI 定义；
- 输入输出；
- 使用场景；
- 不在范围内的内容；
- 与 Harness、WorkAgent 的关系；
- 当前假设。

如果 RSI 的含义会实质影响方案且无法从项目中推断，应提出一个简洁的阻塞问题。

## 任务2：设计 RSI 整体框架

至少包括：

- 数据采集；
- 数据清洗；
- 经验或轨迹存储；
- 样本筛选；
- 训练数据生成；
- 训练或优化模块；
- 评估模块；
- 反馈闭环；
- 版本管理；
- 模型或策略回滚；
- 安全约束；
- 可观测性；
- 与 Harness 的集成。

输出：

- `rsi_architecture.md`
- `rsi_component_design.md`
- `rsi_data_flow.md`
- `rsi_training_flow.md`
- 架构图、数据流图和训练流程图。

## 任务3：制定训练计划

训练计划必须包含：

1. 基线；
2. 数据需求；
3. 数据拆分；
4. 训练阶段；
5. 模型或算法选择；
6. 超参数；
7. 硬件资源；
8. 预计时间；
9. Checkpoint 策略；
10. 评估指标；
11. 对照实验；
12. 消融实验；
13. 重复实验；
14. 早停条件；
15. 失败恢复；
16. Go/No-Go 标准；
17. 实验优先级；
18. 预算估算。

输出：

- `training_plan.md`
- `experiment_matrix.xlsx`
- `resource_budget.xlsx`
- `RSI整体框架与训练计划.docx`
- `RSI整体框架与训练计划.pptx`

第二阶段只交付可执行框架和训练计划，不得将尚未执行的训练写成实际结果。

完成后停止，等待我批准第三阶段。

---

# 第三阶段：数据集与实验

只有第二阶段通过验收后才能执行。

## 任务1：数据集调研

根据 RSI 任务目标搜索公开数据集。

为每个候选数据集记录：

- 名称；
- 官方来源；
- 下载链接；
- 论文或主页；
- 许可证；
- 版本；
- 数据规模；
- 字段；
- 标签；
- 使用限制；
- 与任务的匹配度；
- 潜在数据泄漏风险。

优先选择：

- 来源可验证；
- 许可证允许；
- 可自动下载；
- 与任务匹配；
- 能复现实验的数据集。

不得使用来源不明或许可证不清晰的数据。

## 任务2：获取或构建数据集

如果存在合适的公开数据集：

1. 编写下载脚本；
2. 记录下载时间和版本；
3. 计算文件校验值；
4. 保留原始数据；
5. 生成处理后数据。

如果没有合适数据集，则构建自有数据集，并记录：

- 生成规则；
- 样本来源；
- 采样方法；
- 标注规范；
- 质量控制；
- 随机种子；
- 生成脚本；
- 局限性。

数据目录至少区分：

- raw；
- interim；
- processed；
- train；
- validation；
- test。

## 任务3：数据质量检查

执行：

- 格式验证；
- 缺失值检查；
- 重复数据检查；
- 标签分布检查；
- 异常值检查；
- 训练测试泄漏检查；
- 敏感信息检查；
- 人工抽样复核。

输出：

- `dataset_card.md`
- `dataset_sources.xlsx`
- `data_quality_report.md`
- 数据统计图表。

## 任务4：开始真实实验

按照第二阶段计划：

1. 先运行 Baseline；
2. 再运行优先级最高的正式实验；
3. 使用固定随机种子；
4. 保存完整配置；
5. 保存日志和 Checkpoint；
6. 运行独立评估；
7. 记录所有成功和失败实验。

每次实验至少记录：

- Experiment ID；
- Run ID；
- Git commit；
- 数据集版本；
- 配置文件；
- 随机种子；
- 硬件环境；
- 开始及结束时间；
- 训练耗时；
- Loss；
- 主要指标；
- 次要指标；
- Checkpoint；
- 日志路径；
- 状态；
- 失败原因；
- 复现命令。

结果输出：

- `experiment_results.csv`
- `experiment_results.json`
- `experiment_tracker.xlsx`
- `baseline_report.md`
- `experiment_report.md`

分数必须来自实际评估程序的输出，不得人工估计或补写。

## 任务5：生成第三阶段报告

生成：

- `数据集与实验报告.docx`
- `数据集与实验结果.pptx`
- `实验记录与分数.xlsx`

PPT 和报告必须明确区分：

- 已完成实验；
- 正在运行实验；
- 失败实验；
- 尚未运行实验；
- 当前最佳结果；
- 下一轮实验计划。

### 第三阶段验收条件

- 数据集来源或生成过程可追溯；
- 数据许可证明确；
- 数据划分可复现；
- Baseline 已实际执行；
- 至少一个正式实验已开始或完成；
- 真实分数有日志支持；
- 实验配置和复现命令完整；
- Word、PPT、Excel 文件有效。

---

# 五、Artifact 清单

持续更新：

`project_artifacts/artifact_manifest.md`

每项包含：

- 文件名称；
- 文件路径；
- 所属阶段；
- 文件类型；
- 用途；
- 生成时间；
- 生成方式；
- 校验状态；
- 是否包含真实运行数据。

# 六、每次进度回复格式

每次回复严格采用：

## 当前阶段

说明当前所在阶段和任务。

## 已完成

列出实际完成内容。

## 文件变更

列出新增或修改文件及路径。

## 执行与验证

列出实际执行命令、测试结果和退出码。

## 真实结果

列出已获得的结果及对应证据。

## 问题与风险

列出错误、风险、假设和阻塞项。

## 下一步

说明下一项任务。

## 等待确认

如果到达阶段门禁，明确说明需要我批准什么。

# 七、立即开始

现在立即执行 Phase 1A：

1. 检查项目和环境；
2. 创建 `project_artifacts/execution_plan.md`；
3. 完成仓库审计；
4. 完成 Harness 各组件详细设计；
5. 完成 Pipeline、接口和测试设计；
6. 更新 Artifact 清单；
7. 汇报设计结果；
8. 停止并等待我的批准。

此时不要提前进入 Phase 1B。
