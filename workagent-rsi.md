## 一、建议的研究定位

  建议将项目命名为：
  

  > WorkAgent-RSI: Benchmark-Driven Recursive Skill Improvement for Office Agents
  > 面向办公软件智能体的基准驱动递归技能改进框架

  这里的 RSI 建议定义为 Recursive Skill Improvement，而不是让模型无限制地修改自身代码。

  ### 核心思想

  一个办公技能不应只是几句 Prompt，而应该是一个可测试、可验证、可回滚的软件组件：

  Skill =
  任务描述
  + 工具调用策略
  + 输入输出格式
  + 前置条件
  + 后置条件
  + 示例
  + 验证器
  + 测试用例
  + 风险等级
  + 版本信息

  WorkAgent-RSI 的核心闭环是：

  执行办公任务
     ↓
  记录轨迹和失败
     ↓
  分析失败原因
     ↓
  gen-skill 生成新技能或技能补丁
     ↓
  verify-skill 做静态、动态和安全验证
     ↓
  evaluator-skill 在开发集和隐藏测试集上评分
     ↓
  满足晋级条件后注册为新版本
     ↓
  继续执行下一轮任务

  不建议一开始直接做“自动修改模型权重”。第一阶段做：

  1. Prompt/流程级技能优化；
  2. Tool-use 策略优化；
  3. Python/Office 操作脚本优化；
  4. 验证器和测试用例自动生成；
  5. 后续再考虑模型微调或强化学习。

  ———

  ## 二、相关工作的主要启发

  以下是值得重点调研的方向。具体作者、版本和发表信息，建议让 Codex 在正式调研时再次核验。

   方向                   代表性工作                         对 WorkAgent-RSI 的启发
  ━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   工具调用智能体         ReAct                              将思考、行动、观察结合起来，适合作为办公任务执行框架
  ─────────────────────  ─────────────────────────────────  ────────────────────────────────────────────────────────────
   语言反馈改进           Reflexion                          根据失败轨迹生成文字反馈并用于下一轮改进
  ─────────────────────  ─────────────────────────────────  ────────────────────────────────────────────────────────────
   自我精炼               Self-Refine                        生成—评价—修改循环，但需要更可靠的外部验证器
  ─────────────────────  ─────────────────────────────────  ────────────────────────────────────────────────────────────
   技能库和自动课程       Voyager                            自动积累可复用技能，说明技能应该被版本化和检索
  ─────────────────────  ─────────────────────────────────  ────────────────────────────────────────────────────────────
   自动奖励/评估器生成    Eureka                             LLM 可以帮助生成奖励函数或评估逻辑，但必须防止奖励投机
  ─────────────────────  ─────────────────────────────────  ────────────────────────────────────────────────────────────
   程序化优化             DSPy                               将 Prompt、模块和优化过程结构化，而不是手工调整 Prompt
  ─────────────────────  ─────────────────────────────────  ────────────────────────────────────────────────────────────
   代码执行评估           SWE-bench                          通过实际执行结果评价改进，而不是只依赖语言模型打分
  ─────────────────────  ─────────────────────────────────  ────────────────────────────────────────────────────────────
   电脑操作评测           OSWorld                            强调真实桌面环境下的长链任务执行
  ─────────────────────  ─────────────────────────────────  ────────────────────────────────────────────────────────────
   浏览器/企业任务评测    BrowserGym、WorkArena              说明复杂办公任务需要标准化任务环境和可重复评测
  ─────────────────────  ─────────────────────────────────  ────────────────────────────────────────────────────────────
   LLM 评委               G-Eval、MT-Bench 等                LLM Judge 可以评估主观质量，但不能单独作为最终标准
  ─────────────────────  ─────────────────────────────────  ────────────────────────────────────────────────────────────
   自我修改智能体         Darwin Gödel Machine 等近期工作    强调“提出修改—实际测试—保留有效版本”，而不是无约束自我修改
  ─────────────────────  ─────────────────────────────────  ────────────────────────────────────────────────────────────
   演化式程序优化         AlphaEvolve 等近期工作             可借鉴候选生成、自动测试、精英保留和回滚机制

  ### 当前研究空白

  已有工作通常只解决其中一个问题：

  - 有些工作关注 Agent 执行；
  - 有些工作关注反思或自我改进；
  - 有些工作关注评测；
  - 有些工作关注代码或浏览器任务。

  但针对 PPT、Word、Excel 三类办公软件，统一进行技能生成、验证、评估和版本迭代 的工作相对较少。

  因此，WorkAgent-RSI 可以重点强调以下创新：

  1. 统一的办公技能表示
  2. 生成器、验证器、评估器解耦
  3. 面向最终文件质量的评估，而不仅是文本回复质量
  4. 隐藏测试集和回归测试防止技能过拟合
  5. 跨办公软件的技能迁移
  6. 带安全约束的递归技能改进

  ———

  ## 三、推荐的软件模块

  不要只设计三个模块，建议至少拆成以下六个模块：

  ### 1. orchestrator-skill

  负责整个 RSI 流程：

  - 选择任务；
  - 调用当前技能；
  - 记录轨迹；
  - 触发失败分析；
  - 调度生成、验证和评估；
  - 管理技能晋级和回滚。

  ### 2. gen-skill

  输入：

  - 失败任务；
  - Agent 执行轨迹；
  - 生成的办公文件；
  - evaluator 的错误报告；
  - 现有技能版本。

  输出：

  - 新技能或技能补丁；
  - 修改原因；
  - 预期改进点；
  - 新增测试用例；
  - 需要验证的假设。

  注意：gen-skill 只能生成候选版本，不能直接上线。

  ### 3. verify-skill

  负责验证候选技能：

  - Skill Manifest 格式检查；
  - 工具调用合法性检查；
  - 权限检查；
  - 沙箱执行；
  - Office 文件格式检查；
  - 公式、引用、链接检查；
  - 是否引入危险命令；
  - 是否破坏已有任务。

  ### 4. evaluator-skill

  负责给任务和文件打分，应该尽量独立、版本固定、不可被待测技能修改。

  建议评分维度：

  总分 =
  语义正确性
  + 结构正确性
  + 视觉质量
  + 工具执行效率
  + 安全性

  对不同应用使用不同评估器：

  #### Excel

  - 单元格数值是否正确；
  - 公式是否正确；
  - 是否存在 #REF!、#VALUE! 等错误；
  - 汇总、透视表、图表是否正确；
  - 格式、列宽、冻结窗格是否符合要求。

  #### Word

  - 标题层级；
  - 段落和样式；
  - 表格；
  - 页眉页脚；
  - 引用和目录；
  - 是否存在溢出、空白页、格式错误；
  - PDF 渲染后的视觉质量。

  #### PPT

  - 页数；
  - 文字内容；
  - 版式；
  - 元素重叠；
  - 文字溢出；
  - 图表和图片位置；
  - 字体、颜色和主题一致性；
  - PDF/图片渲染结果。

  ### 5. skill-registry

  保存技能版本：

  id: excel.monthly_report
  version: 0.3.0
  domain: excel
  description: 生成月度销售分析表
  inputs:
    - raw_sales_file
  outputs:
    - xlsx_report
  tools:
    - python
    - libreoffice
  preconditions:
    - 输入文件存在
  postconditions:
    - 所有公式可计算
    - 不存在错误单元格
  risk_level: medium
  tests:
    - tests/excel/monthly_report_001.yaml
  dependencies:
    - excel.clean_data

  ### 6. trace-memory

  保存：

  - 任务；
  - 工具调用；
  - 中间状态；
  - 错误；
  - evaluator 结果；
  - 技能版本；
  - 改进前后对比。

  ———

  ## 四、建议的评测策略

  不能只使用 LLM Judge。建议采用三层评估：

  ### 第一层：硬性断言

  例如：

  文件是否能打开
  公式是否能重新计算
  是否存在错误单元格
  页数是否正确
  指定文本是否存在
  指定表格是否存在

  ### 第二层：结构和视觉评估

  - OOXML 结构解析；
  - PDF 渲染；
  - 图片相似度；
  - OCR；
  - 元素重叠检测；
  - 版式检查。

  ### 第三层：语义质量评估

  - LLM Judge；
  - 人工抽检；
  - 多评委交叉评价；
  - 对评委进行人工校准。

  必须设置：

  - 训练集；
  - 开发集；
  - 隐藏测试集；
  - 回归测试集；
  - 对抗测试集。

  候选技能只有在以下条件同时满足时才能晋级：

  1. 通过安全和格式检查；
  2. 开发集分数超过当前版本；
  3. 隐藏测试集没有明显退化；
  4. 关键任务不能失败；
  5. 没有引入新的高风险行为；
  6. 可复现；
  7. 保存完整版本和评估证据。

  ———

  # 可直接复制给 Codex 的 Prompt

  你是一名 Principal Research Engineer 和 ML Systems Researcher。请帮助我设计并实现一个研究项目：

  WorkAgent-RSI
  Benchmark-Driven Recursive Skill Improvement for Office Agents

  项目目标：
  构建一个面向 PPT、Word、Excel 办公任务的递归技能改进框架。系统能够执行办公任务，记录失败轨迹，自动生成技能改进候选，通
  过独立验证器和评估器进行筛选，最终将有效技能注册为新版本，并支持回滚、回归测试和跨任务迁移。

  一、术语定义

  这里的 RSI 指 Recursive Skill Improvement，而不是无限制地修改模型权重。

  Skill 不是简单 Prompt，而是一个可版本化的软件组件，至少包含：

  - 任务描述
  - 触发条件
  - 输入和输出
  - 工具调用策略
  - 前置条件
  - 后置条件
  - 测试用例
  - 验证规则
  - 风险等级
  - 依赖技能
  - 版本号
  - 成功和失败示例

  第一阶段只实现：
  1. Prompt/流程级技能优化；
  2. Tool-use 策略优化；
  3. Office 操作脚本优化；
  4. 验证器和测试用例生成。

  暂时不要实现模型权重级别的自我训练。

  二、先进行文献和相关工作调研

  请先调研 2023—2026 年与以下主题相关的论文、项目和基准：

  - ReAct
  - Reflexion
  - Self-Refine
  - Voyager
  - DSPy
  - Eureka
  - SWE-bench
  - OSWorld
  - BrowserGym
  - WorkArena
  - AgentBench
  - G-Eval
  - MT-Bench
  - LLM-as-a-Judge
  - AgentDojo 或其他工具调用安全评测
  - Darwin Gödel Machine
  - AlphaEvolve 或其他演化式程序优化方法
  - PPT、Word、Excel、Spreadsheet、Office Agent 相关基准

  检索要求：

  1. 优先使用 arXiv、ACL Anthology、OpenReview、会议官网、官方 GitHub；
  2. 每篇工作必须给出可验证的论文链接或项目链接；
  3. 不要编造论文、作者、年份或实验结果；
  4. 区分同行评审论文、预印本、工程项目和产品文档；
  5. 对每项工作总结：
     - 问题设置；
     - 核心方法；
     - 评估方式；
     - 对 WorkAgent-RSI 的启发；
     - 存在的不足；
  6. 重点回答：
     - 现有工作如何进行 Agent 自我改进？
     - 如何定义和存储技能？
     - 如何验证技能是否真的变好？
     - 如何避免技能过拟合评估器？
     - 如何评估 PPT、Word、Excel 生成文件？
     - WorkAgent-RSI 的研究空白和可能创新是什么？

  请生成：

  docs/literature_review.md

  三、提出正式的问题定义

  请生成：

  docs/problem_definition.md

  明确：

  1. 任务空间；
  2. 技能的数学或程序化表示；
  3. 执行轨迹；
  4. 失败类型；
  5. 技能改进操作；
  6. 评估函数；
  7. 晋级条件；
  8. 回滚条件；
  9. 安全边界；
  10. 研究假设。

  至少提出以下假设：

  H1：模块化的 gen-skill、verify-skill、evaluator-skill 比单体式自我反思更容易控制和调试。

  H2：加入独立验证器可以降低技能改进导致的回归问题。

  H3：Office 文件级评估比只评价最终自然语言回复更能反映任务成功率。

  H4：在 Excel 上获得的部分数据处理技能可以迁移到 Word 和 PPT 的文档生成流程中。

  H5：隐藏测试集和回归测试可以降低技能针对评估器的过拟合。

  四、设计总体架构

  请生成：

  docs/architecture.md

  系统至少包含以下模块：

  1. orchestrator-skill
  2. gen-skill
  3. verify-skill
  4. evaluator-skill
  5. skill-registry
  6. trace-memory
  7. executor
  8. artifact-store
  9. benchmark-runner
  10. promotion-and-rollback

  请提供：

  - 系统架构图；
  - 组件职责；
  - 数据流；
  - API 接口；
  - 错误处理；
  - 版本管理；
  - 失败恢复；
  - 安全边界；
  - 哪些组件必须只读或不可被待测技能修改。

  五、设计 Skill Manifest

  请实现一个可扩展的 Skill Manifest，使用 YAML 或 JSON。

  至少包含：

  - id
  - version
  - domain
  - description
  - triggers
  - inputs
  - outputs
  - tools
  - preconditions
  - postconditions
  - risk_level
  - dependencies
  - examples
  - tests
  - evaluator_config
  - rollback_policy

  请为以下技能提供示例：

  1. excel.monthly_report
  2. word.house_style
  3. ppt.executive_summary

  六、实现三个核心模块

  A. gen-skill

  输入：

  - 任务定义；
  - 失败轨迹；
  - 生成文件；
  - evaluator 结果；
  - 当前技能版本；
  - 历史改进记录。

  输出：

  - 候选 Skill Manifest；
  - Prompt 或代码补丁；
  - 改进说明；
  - 失败原因分析；
  - 新增测试；
  - 预期改进指标。

  要求：

  - 只能生成候选版本；
  - 不能直接部署；
  - 必须输出结构化结果；
  - 不能修改 evaluator；
  - 对所有修改提供 rationale。

  B. verify-skill

  至少实现：

  - Manifest schema 校验；
  - 工具和权限校验；
  - 沙箱执行；
  - 输入输出校验；
  - 文件格式检查；
  - Office 文件是否可打开；
  - Excel 公式错误检查；
  - Word/PPT XML 结构检查；
  - 危险命令检测；
  - 回归测试；
  - 资源和超时限制。

  输出 VerificationReport：

  - pass/fail；
  - violations；
  - warnings；
  - counterexamples；
  - executed_tests；
  - reproducibility_info。

  C. evaluator-skill

  请实现可配置的多维度评估器。

  基础维度：

  - semantic_correctness
  - structural_correctness
  - visual_quality
  - execution_efficiency
  - safety
  - regression_score

  必须先执行 critical failure gate，再计算加权总分。

  默认分数可以使用：

  - 语义正确性：0.30
  - 结构正确性：0.25
  - 视觉质量：0.20
  - 执行效率：0.10
  - 安全性：0.15

  但权重必须可配置。

  七、实现 Office 专用评估器

  Excel：

  - 单元格值断言；
  - 公式断言；
  - 公式重新计算；
  - 错误单元格检查；
  - 汇总和透视表检查；
  - 格式、列宽、冻结窗格；
  - 图表存在性和基本属性。

  注意：不要把 openpyxl 读取公式等同于完成公式计算。必要时使用 LibreOffice headless 或其他可复现的计算环境。

  Word：

  - 文档是否可打开；
  - 标题层级；
  - 样式；
  - 表格；
  - 页眉页脚；
  - 目录；
  - 引用；
  - 空白页和分页；
  - PDF 渲染；
  - 视觉质量。

  PPT：

  - 页数；
  - 指定文本；
  - 标题层级；
  - 元素重叠；
  - 文本溢出；
  - 图片和图表；
  - 主题颜色；
  - 字体；
  - 页面视觉一致性；
  - PDF 或 PNG 渲染结果。

  八、设计 Benchmark

  请建立统一任务格式，至少包括：

  - task_id
  - domain
  - input_files
  - instruction
  - expected_constraints
  - hard_assertions
  - visual_requirements
  - semantic_requirements
  - risk_level
  - grader_config
  - hidden_test_flag

  第一版任务规模：

  - Excel：10 个任务；
  - Word：10 个任务；
  - PPT：10 个任务；
  - 每个领域包含 easy、medium、hard；
  - 其中一部分作为隐藏测试集；
  - 另外加入回归测试和对抗测试。

  优先做三个可运行 Demo：

  1. Excel：清洗销售数据并生成月度分析表；
  2. Word：将原始文档转换为统一公司模板；
  3. PPT：根据一份结构化输入生成 5 页管理层汇报。

  如果本机没有完整 Office 软件，请实现：
  - 可运行的 mock executor；
  - 清晰的 adapter 接口；
  - LibreOffice 可选适配；
  - 不要伪装成已经完成真实 Office 验证。

  九、实现 RSI 主循环

  请实现如下流程：

  1. 读取 benchmark task；
  2. 加载当前 champion skill；
  3. 执行任务；
  4. 保存完整 trace 和 artifact；
  5. 调用 evaluator；
  6. 如果失败，生成 failure diagnosis；
  7. 调用 gen-skill；
  8. 调用 verify-skill；
  9. 在开发集、回归集和隐藏测试集上评估；
  10. 根据 promotion policy 决定接受或拒绝；
  11. 保存版本、指标和证据；
  12. 支持 rollback。

  默认晋级策略：

  - 必须通过所有 critical safety checks；
  - 开发集总分有显著提升；
  - 隐藏测试集不能出现明显退化；
  - 关键任务不能从成功变为失败；
  - 新技能必须能够复现；
  - 高风险技能需要人工批准；
  - evaluator 本身不能由待测技能修改。

  十、实验设计

  请给出以下 baseline：

  1. 固定 Prompt、无 RSI；
  2. 单体式 Self-Refine；
  3. 只有 gen-skill；
  4. gen-skill + verify-skill；
  5. gen-skill + verify-skill + evaluator-skill；
  6. 完整 WorkAgent-RSI。

  比较指标：

  - task success rate；
  - artifact correctness；
  - visual quality；
  - regression rate；
  - hidden-test performance；
  - average number of iterations；
  - execution cost；
  - latency；
  - unsafe action rate；
  - cross-domain transfer。

  请生成：

  docs/evaluation_protocol.md
  docs/experiment_plan.md

  十一、工程实现要求

  建议技术栈：

  - Python 3.11+
  - Pydantic
  - pytest
  - SQLite 或 DuckDB
  - Typer CLI
  - 可选 FastAPI
  - 可选 LibreOffice headless
  - 可选 Docker sandbox

  要求：

  1. 先写 schema 和接口，再写实现；
  2. 所有核心模块提供单元测试；
  3. 提供至少一个端到端测试；
  4. 使用类型注解；
  5. 记录结构化日志；
  6. 所有技能和评估器均版本化；
  7. 不允许静默失败；
  8. 不允许执行未授权的系统命令；
  9. 不允许把待测技能生成的结果直接当作评估标准；
  10. 不要过早引入复杂的模型微调系统。

  推荐目录：

  workagent-rsi/
  ├── docs/
  ├── src/workagent_rsi/
  │   ├── orchestrator/
  │   ├── gen_skill/
  │   ├── verify_skill/
  │   ├── evaluator_skill/
  │   ├── executor/
  │   ├── registry/
  │   ├── memory/
  │   └── benchmark/
  ├── skills/
  │   ├── excel/
  │   ├── word/
  │   └── ppt/
  ├── benchmark/
  ├── tests/
  ├── examples/
  ├── pyproject.toml
  └── README.md

  十二、最终交付

  请最终输出：

  1. 文献调研报告；
  2. 问题定义；
  3. 系统架构；
  4. Skill Manifest schema；
  5. gen-skill、verify-skill、evaluator-skill 的接口和初始实现；
  6. 三类 Office Demo；
  7. Benchmark 格式；
  8. 评估协议；
  9. 实验计划；
  10. 单元测试和端到端测试；
  11. README；
  12. 已知限制和下一阶段计划。

  请先完成调研、问题定义和架构设计，再开始编码。每完成一个阶段，都要说明：
  - 已完成内容；
  - 未解决问题；
  - 设计取舍；
  - 下一步行动。

  ## 五、最推荐的落地顺序

  不要一开始同时把三个软件全部做深，建议：

  1. 第一阶段：Excel
      - 公式和单元格容易做自动断言；
      - 评估器更容易客观化；
      - 可以先验证 RSI 闭环。

  2. 第二阶段：Word
      - 加入结构和 PDF 渲染评估；
      - 研究格式迁移和模板技能。

  3. 第三阶段：PPT
      - 加入视觉布局、重叠、溢出、风格一致性；
      - 这是最难、也最能体现研究价值的部分。

  最关键的原则是：

  > gen-skill 可以提出改进，verify-skill 决定是否安全可执行，evaluator-skill 决定是否真的变好，orchestrator 决定是否晋
  > 级。

  这样比让一个 Agent 自己“反思并修改自己”更容易形成可靠的研究系统，也更适合写论文和做可重复实验。