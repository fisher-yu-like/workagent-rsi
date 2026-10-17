# Evaluation/RSI hardening design constraints (frozen source extract)

Source: local WorkAgent_RSI_Codex_Execution_Plan_20261016.md, section 2; copied on 2026-10-17 for T00. This is a design contract, not a completed implementation report.

## 2. 随计划交付的设计与验收约束

### 2.1 模块职责

| 模块 | 职责 | 无权执行的动作 |
|---|---|---|
| RequirementInventory / SpecAdmission | 将任务原文和来源映射成冻结要求，检查需求覆盖 | 看见产物后降低规格 |
| SandboxExecutor | 在真实OS边界内执行模型代码，导出允许产物 | 读取保护资料、继承密钥、挂载宿主仓库 |
| SharedAssessment | 在同一证据快照中完成独立oracle/定位/渲染/judge观察 | 优化候选、修文件、修改要求 |
| ArtifactEvaluator | 按冻结要求计算范围明确的分数、接受和覆盖 | 用缺项推测总分、悄悄重配权重 |
| ArtifactVerifier + TraceDiagnosis | 提供缺陷事实、原因假设、最小修复与复查项 | 把缺口当成品错误、编造根因 |
| RepairLoop | 修复当前任务；预算内重跑并全项复查 | 修改全局技能、取得保护集答案 |
| CandidateProvider / CandidateVerifier | 根据champion和develop提出并验证instructions修改 | 部署、改评估器、修改安全策略 |
| RSI / Promotion / Registry | 比较配对证据、保留或拒绝版本、记录回滚 | 将pilot声明为正式收益、覆盖历史 |

### 2.2 三个覆盖口径

- **task_requirement_coverage**：已核对需求中，多少有验收方法与对应check。未审核需求清单不能声称100%需求覆盖。
- **check_completion**：声明的适用检查中，多少实际完成。它沿用旧coverage含义，不代表需求完整。
- **evidence_scope**：模型/渲染实际覆盖了哪些页、对象、片段和来源；未覆盖范围必须列出。

任务分数只有在相应profile规格准入且所需检查完成时才可解释。结构检查分数独立显示，不能代替task_acceptance。

### 2.3 状态与学习信号

| 原因 | 任务指标 | 质量指标 | 自动下一步 |
|---|---|---|---|
| 环境/API/引擎缺失 | unavailable，不当失败0分 | null | 恢复能力或阻断该真实实验 |
| 模型代码/交付失败 | 计执行失败和任务不成功 | 未观察维度null | develop可见轨迹诊断与预算内修复 |
| 成品确认缺陷 | FAIL/PARTIAL | 按观察评分 | develop问题反馈与修复 |
| checker错误/证据不足 | incomplete/needs_review | 对应维度null | 修评估能力或人工复核，不诱导修改正确产物 |
| 需求不清/未映射 | SPEC_INCOMPLETE | 不发布任务总分 | 澄清或补齐规格 |

质量比较不能通过删掉失败任务获利。不同原因有各自计数与分母；后续门禁使用预注册主指标。已确认关键缺陷不会因另一通道缺失而消失，但缺失通道不补分。

### 2.4 允许复用与禁止过拟合

允许：读取/保存/渲染库、通用API说明、按当前输入范围运算的算法、用户授权的具体版式与模板。

禁止：benchmark/task_id选择答案、固定题目数值/标题/结论、绕过读取当前输入、把所有任务约束到固定Summary/固定三页、把保护集反馈写进技能、靠删检查提升分数。

不能以“代码每次都不一样”判断动态Agent。判据是输入观察可追溯、授权任务决策正确、受控输入变体下行为正确；参数化通用算法可以合法复用。

### 2.5 数据与模型评估协议

1. develop详细反馈可用于当前任务修复和公开技能经验；regression/promotion_validation/OOD/final保持评估侧权限。
2. promotion_validation会反复用于选择，不能当完全封存测试；final_test在候选选择完成后一次性使用。
3. 切分单位为家族和源文件；同源变体不得跨split。最终集开发人员只见哈希/计数，不查看内容优化。
4. baseline/candidate使用相同规格、预算和评估配置；保留全部重复与失败调用；不只挑最好一次。
5. 旧报告不混合计算；需比较历史版本时，在新冻结reference set上分别重评并保留新记录。
6. 新真实provider使用显式模型ID与实际调用记录，不根据聊天助手身份或模型自报补造。
7. 首批工程构造任务有规模目标，不授权立即运行216实例×多组×多轮真实调用；所有调用先dry-run和用户预算。

### 2.6 接口与版本规则

本计划中 `TaskSpec`、`AcceptanceSpec`、`Assessment`、`ArtifactIssue`、`EvaluationContract`、`CandidatePatch`、`WorkAgentSkill` 沿用现有类型，扩展时提供旧数据读取适配。新类型所属文件在各task中定义。计划中的 `dict` 表示JSON可序列化对象，字段按所属task落实为Pydantic模型，拒绝未声明字段。

状态新增采用版本化schema，不把字符串塞进旧bool字段；旧公共入口默认兼容调用，内部统一调用新语义。评估代码、规格、提示词、工具、渲染器或judge配置变更产生新身份，不在旧cohort里继续比较。候选技能变化只改变skill身份，评估侧冻结。

### 2.7 真实调用配置与人工介入

T03建立共用 `live_call_policy.json` 模型：`allow_live_calls=false`、`approved_by_user=false`、provider、model、endpoint、max_model_calls、max_tool_calls、max_wall_seconds、max_cost_usd、批准时间/来源。真实调用前所有适用上限必须有具体数值并由用户确认；费用无法观测时以用户认可的调用/token/时间硬上限替代，不默认无限。

只在以下情况请求用户：凭据/账户接入、安装与系统/Officeworker配置、无法判断的任务要求、人工盲标、预算不足或需外部发布/许可决定。用户已有授权且范围未变时不重复询问。受阻task写blocked原因并继续独立离线task，不能以elapsed time当批准。
