# WorkAgent-RSI 文献调研报告

> 调研日期：2026-09-22  
> 项目：WorkAgent-RSI: Benchmark-Driven Recursive Skill Improvement for Office Agents

## 1. 调研范围与来源

本报告重点分析两篇用户指定的 arXiv 工作，并将其结论映射到办公软件智能体的可验证递归技能改进框架。

| 工作 | 类型 | 原文 | 本地来源 |
|---|---|---|---|
| RRSI: Regularized Recursive Self-Improvement of Agent Harnesses | arXiv 预印本，方法研究 | https://arxiv.org/abs/2609.24972 | `docs/sources/rrsi-2609.24972.html` |
| The Last AI Built by Humans: Toward Genuine Recursive Self-Improvement | arXiv 预印本，综述与框架 | https://arxiv.org/html/2609.11873 | `docs/sources/genuine-rsi-2609.11873.html` |

两篇工作均属于预印本，不将其结果表述为已经经过同行评审的定论。RRSI 的原文实验使用冻结 backbone，研究对象是 agent harness；第二篇工作主要提出 RSI 定义、自治等级和评价要求，并明确区分当前系统变强与“改进后继系统的能力”变强。

## 2. 工作一：RRSI

### 2.1 问题设置

RRSI 将 agent 的 prompt、控制流、工具、记忆、上下文管理和子代理等统称为 harness。系统在固定的 evolve split 上反复提出和选择 harness 编辑。问题是：有限评测集被多轮自适应访问后，分数提升可能来自任务记忆、评估噪声或无节制的资源增长，而不是可迁移的机制改进。

RRSI 不直接缩小可编辑空间。它保留 prompt、控制流、工具、技能、记忆和子代理等组件都可变的假设空间，改为约束搜索轨迹和候选进入永久状态的条件。

### 2.2 方法结构

RRSI 把约束分成两侧：

1. **Proposal-side regularization**：限制每轮候选的自适应容量。
   - 退火的编辑预算：早期允许较多协调编辑，后期逐渐减少，改善归因能力。
   - 证据感知的 credit assignment：保存每个候选修改的组件、假设、差异、分数/成本变化和是否接受；被拒绝的机制成为负证据。
   - 结构化探索：若近期进展落入经验噪声带，则把一部分预算分配给尚未探索的组件，避免只反复改 prompt。

2. **Selection-side regularization**：限制哪些候选可以成为新 incumbent。
   - 泄漏筛查：在完整评估前拒绝编码任务名、实体名、答案、任务特定数值或无效装饰逻辑的修改。
   - 稳定性门槛：先估计未修改基线的经验噪声带，候选不得因为小幅随机波动导致持续退化。
   - 成本感知接受：分数收益必须支付新增 token、步骤或工具成本，禁止单纯扩大 harness。
   - 结构剪枝：长期没有严格正收益的组件成为删除候选。

### 2.3 评估设计与主要证据

原文在 coding、agentic workspace 和 engineering design 三类场景评估，并使用 evolve、ID held-out 和 OOD benchmark。其核心证据不是 evolve split 的最高分，而是：

- evolve split 提升较小但 held-out/OOD 仍提升；
- deterministic simulator/testbench 的 engineering design 结果也改善，降低 judge gaming 的解释空间；
- harness 在未参与搜索的 policy/model 上仍有迁移收益；
- 正则化消融显示，去掉 proposal 或 acceptance 约束都会提高 evolve 分数但损害 OOD 转移，并增加 token 成本；
- 最终 harness 的成本低于无约束演化方案，但高于未演化基线，说明成本是显式的质量-资源权衡。

报告中给出的代表性数字包括：RRSI 在其任务设置下最多获得 14.1 个 evolve split 分数点和最多 4.7 个 OOD 分数点，同时比未正则化演化减少约 30% policy tokens。这里仅记录原文报告值，不将其外推为 WorkAgent-RSI 的预期结果。

### 2.4 对 WorkAgent-RSI 的直接启发

| RRSI 机制 | WorkAgent-RSI 落地方式 |
|---|---|
| 原子编辑与编辑预算 | `SkillPatch` 只允许修改 manifest 字段、prompt/tool policy、脚本或测试中的受控集合；每轮限制 patch 数量并后期退火 |
| 证据感知历史 | `trace-memory` 保存候选 diff、失败假设、任务 split、分数、成本、验证结果和接受决定 |
| 泄漏筛查 | `verify-skill` 对任务名、答案、输入值硬编码、危险命令、评估器修改和无效代码做静态检查 |
| 稳定性门槛 | `evaluator-skill` 对 champion 重复运行，估计噪声带；候选必须超过噪声容限且不得破坏 protected regression set |
| 成本感知选择 | 晋级策略同时读取成功率、文件质量、token/步骤/耗时和安全风险 |
| 结构剪枝 | 版本注册表标记长期无效的技能步骤、工具或验证规则，允许候选删除而非只累加 |
| OOD/跨模型转移 | Excel 开发集之外保留 Word/PPT、跨模板和未见输入任务；后续可用不同 executor/model 做 transfer |

### 2.5 局限与工程警示

- 仍依赖有限 evolve set 和人工设定的正则化超参数，不能自动消除数据偏差。
- 结果是 harness-level RSI，不等同于模型权重自我训练。
- 复杂工具生态、长时间运行和 Office 文件渲染可能引入新的非平稳性。
- 如果 evaluator 与候选技能共用可修改状态，泄漏筛查和分数都不再可信。
- 成本指标必须可追溯到每次运行，不应只报告最终分数。

## 3. 工作二：Genuine RSI 框架

### 3.1 定义

第二篇工作把 RSI 定义为：智能系统通过持续任务/环境交互，将经验与反馈转化为跨轮次持久的自身变化，而且这些变化能够进一步影响后续自我改进的生成、评估、选择或巩固机制。该定义强调两个条件：变化必须持久，并且要影响后续改进过程；一次性的自我反思或任务代码修改不足以证明完整 RSI。

### 3.2 五级自治层次

| 层级 | 重点 | WorkAgent-RSI 对应边界 |
|---|---|---|
| B0 | 单任务内改进 | 一次任务中的重试/反思，不记入技能版本 |
| L1 | 改进执行自治 | 系统按人定义的 gen/verify/evaluate 流程执行候选改进 |
| L2 | 改进策略自治 | 系统根据失败诊断选择改 prompt、工具、脚本、记忆或测试的策略 |
| L3 | 未来经验获取自治 | 系统按当前弱点选择下一批 benchmark 任务或生成练习任务 |
| L4 | 部署与环境适应自治 | 系统决定哪些经验持久化为 skill、memory 或 harness，并在新任务中调用 |
| L5 | 元改进自治 | 系统修改并继承 gen、verify、evaluator 或 orchestrator 的改进机制 |

本项目第一阶段目标限定在 L1，允许受控的 L2 候选生成；不声称实现 L3-L5。只有当后续实验能证明一个改进机制被继承并用于生成/选择下一轮候选时，才可讨论结构性 L5。

### 3.3 评价要求

该工作强调需要区分“当前 agent 变强”和“产生后继改进的过程变强”。建议记录：

- 适应性：每轮增益、达到目标所需时间/轮数；
- 保留性：原有任务是否退化；
- 转移：held-out、跨域和跨模型收益；
- 效率：token、时间、成本和每个验证增益的资源消耗；
- 稳定性：有害更新、最大暂时下降和恢复情况；
- 元递归：被修改的机制是否在后续轮次被调用，以及后继质量是否提升。

第二篇工作还提出，长期状态必须关联证据、适用条件、依赖和后续效果；技能库不能只做无条件累加，否则会出现检索漂移、错误复用和旧能力被覆盖。

### 3.4 对 WorkAgent-RSI 的直接启发

1. **显式权限边界**：目标、protected test、资源预算、工具授权和最终发布权由项目外部固定；待测 skill 不能修改 evaluator、隐藏集或 promotion policy。
2. **状态与证据绑定**：每个 skill version 必须保存 parent version、patch、动机、运行配置、评估输出、接受理由、适用条件和回滚点。
3. **跨组件诊断**：失败不直接等同于 prompt 错误。诊断应产生可检验的 intervention hypothesis，并区分数据、上下文、工具、executor、artifact 和 evaluator 问题。
4. **分层评估**：先做硬断言和结构检查，再做渲染/视觉检查，最后才允许 LLM judge 作为语义补充。
5. **长期实验**：记录被拒绝候选、回归、恢复、成本和后续使用情况，避免只保存最佳版本。
6. **L5 证据门槛**：如果将来修改 evaluator 或 improver，必须使用冻结 epoch、独立 anchor、受控重评估和可回滚版本，不能让分数标准随候选任意改变。

## 4. 综合设计原则

两篇工作合并后，对 WorkAgent-RSI 形成以下不可省略的设计原则：

### 4.1 生成、验证、评估、发布解耦

`gen-skill` 可以提出候选但不能上线；`verify-skill` 负责合法性、安全、格式和回归；`evaluator-skill` 只读且版本冻结；`orchestrator` 根据 promotion policy 决定注册或拒绝。这样才能分别定位“不会做”“不安全”“没有变好”和“发布错误”。

### 4.2 评估器优先独立，且先硬后软

Office 文件必须首先通过真实格式读取、公式/结构检查和可渲染性验证。语义 judge、视觉模型或人工抽检只作为补充。待测技能生成的结果不能反过来定义评估标准。

### 4.3 以 protected split 抵抗过拟合

每个领域至少拆分 develop、regression、hidden-test、OOD/transfer 和 adversarial 任务。晋级要求 develop 有有效增益，regression 无关键退化，hidden/OOD 不出现明显下降，并报告每个 split 的真实输出。

### 4.4 资源与收益同时计量

成功率之外必须记录 token、工具调用数、步骤数、耗时、磁盘/渲染成本和人工审核时间。候选只有在增益足以支付成本时才应晋级。

### 4.5 先做可验证的 Office 闭环

建议实现顺序仍为 Excel -> Word -> PPT。Excel 先验证单元格、公式和错误值断言；Word 增加 OOXML、样式和 PDF 渲染；PPT 最后加入版式、重叠、溢出和视觉一致性。第一阶段只做 Harness + WorkAgent Pipeline 设计与最小可运行接口，不提前声称 Office 真实运行成功。

## 5. WorkAgent-RSI 的研究空白与可检验假设

### 5.1 研究空白

- 缺少针对 PPT、Word、Excel 的统一 skill 表示与跨域迁移评估。
- 现有 RSI/agent evolution 工作较少把最终 Office artifact 的结构和视觉质量放进晋级闭环。
- evaluator 独立性、隐藏测试、版本证据和回滚通常没有与技能生成统一建模。
- “当前任务得分变高”与“后续改进能力变强”之间缺少可重复的长程实验协议。

### 5.2 首轮假设

- H1：模块化的 gen/verify/evaluator 比单体式自我反思更容易定位错误并调试。
- H2：独立验证器和 protected regression set 可以降低技能更新造成的回归。
- H3：Office 文件级硬断言、结构检查和渲染检查比只评估自然语言回复更能反映真实任务成功率。
- H4：Excel 数据清洗与结构化输出技能中的部分机制可以迁移到 Word/PPT 生成流程，但迁移收益需要独立测量。
- H5：hidden/OOD split、泄漏筛查和成本约束可以降低对 evolve/evaluator 的过拟合。

## 6. 结论

RRSI 提供了“如何约束搜索轨迹”的工程机制；第二篇工作提供了“如何定义自治边界和证明继承性”的研究标准。WorkAgent-RSI 的首个可交付闭环应因此限定为：固定目标和评估器，生成受控候选，进行静态/动态/Office 文件验证，在开发、回归和隐藏集上独立评分，满足安全、收益、成本和可复现性条件后才注册新技能版本。任何模型权重自训、自动修改评估目标或无人值守的 L5 元改进，都放到后续阶段并设独立门禁。

