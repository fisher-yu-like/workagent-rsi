# Office Harness 与 RSI 下一步计划

> 执行方式：可将独立的代码审阅、能力审计和测试并行推进；依赖真实 provider 结果的 Office/RSI 任务仍按产物依赖顺序执行。不使用 Ollama。Provider 身份、调用方式与模型判断通道必须如实记录。

**目标：** 在保留简洁 Harness 入口的前提下，先确认当前 provider 路径，再跑通一个真实 Office 文件的完整“生成—评估—定位—修复—复评—晋级”闭环，之后逐步验证 Word、Excel、PowerPoint 的统一链路。

**架构：** `Harness/Run` 继续作为单任务入口；格式检查、语义/视觉评估和 verifier 复用当前已接入的 `SharedAssessment`、`ArtifactEvaluator`、`ArtifactVerifier`；RSI 通过 `WorkAgentExperimentRunner` 和 `RSILoop` 执行。候选只能改变 `skill.json` 允许字段，不能改 evaluator、verifier、测试门禁或 protected split。先以一个 XLSX 打通端到端，再用同一入口依次覆盖 DOCX、PPTX。每轮保存任务、输入/产物哈希、provider 元数据、score/issues 报告、candidate diff、验证结果、晋级 gate 与 checkpoint。

**技术栈：** Python 3.12、现有 `workagent_rsi`、pytest、项目 Office fixture、当前配置的非 Ollama provider；Office 读写沿用项目依赖和经验证的本机 Office 能力。

**现有依据：** 当前执行计划、Office qualification 报告和 artifact assessment/RSI 代码；历史基础资格结果不等同于本分支当前提交的完整三域 artifact-v1 闭环。

## 全局约束

- 工作分支：`codex/merge-office-artifact-assessment`；除非用户另行要求，不直接合入其他分支或推送。
- Provider 不使用 Ollama；记录实际 provider、模型 ID、版本、调用状态和成本可用性，不伪造模型调用。
- `project-generated` fixture 只作工程验证，不宣称外部 benchmark。
- `hidden` split 不进入候选生成上下文，只能经冻结评估器用于晋级门禁。
- 任何必需评估通道缺失或不完整时，分数保持 `null/INCOMPLETE`，不以零分或推测值补齐。
- RSI 候选必须通过 allowlist、leakage、patch schema、compile、候选测试及 artifact execution config 检查；失败候选不得改变 champion。
- 全流程串行执行；阶段间保存结果并检查后再继续。

---

## 阶段 1：确认实际执行能力

**检查范围：** `src/workagent_rsi/workagent_provider.py`、`src/workagent_rsi/model_judgement.py`、`src/workagent_rsi/office_capabilities.py`、`project_artifacts/formal_study/stage1_manifest.json`。
**产物：** `project_artifacts/formal_study/provider_capability_20261011.json`。

- [ ] 核实本机 CLI/API 的实际 provider 与模型，不读取或输出密钥。
- [ ] 若使用 Codex CLI，检查命令是否仍含 `--oss`、`--local-provider ollama`；若需修复，先加测试并确认测试失败，再改实现和测试。
- [ ] 探测 Microsoft Office COM 与可用渲染器；分别记录 Word、Excel、PowerPoint 重开与图像渲染能力。
- [ ] 执行只读结构化模型连通性检查；若不可用则记录 `unavailable`。当前对话助手只能作为明示的人工输入来源，不能记录成被程序调用的 provider。
- [ ] 写入含日期、分支/commit、provider 名称/版本、能力状态和失败原因的 JSON；不得记录密钥。

**验收：** 明确确认是否有真实非 Ollama provider、语义判断、视觉图像判断和 Office 重开能力；连通性结论可由日志复查。

**2026-10-11 执行状态：** 已将 `codex-cli` 后端的命令构造改为不传 `--oss` / `--local-provider ollama`，默认模型改为 `gpt-5.4`，并将记录身份改为 `codex-cli:gpt-5.4`。新增 provider 命令契约测试已通过。真实 Codex CLI 连通性探测启动成功但在采样请求阶段持续超时并连接失败，未得到模型响应；证据与能力状态记录在 `project_artifacts/formal_study/provider_capability_20261011.json`。在连接恢复前，不进入“已跑通真实模型内循环”的结论。

## 阶段 2：单一 Excel 内环闭环

**检查范围：** `src/workagent_rsi/workagent_experiment.py`、`workagent_evaluator.py`、`artifact_assessment.py`、`artifact_evaluator.py`、`artifact_verifier.py`、`rsi_loop.py`。
**结果目录：** `project_artifacts/results/rsi-live-20261011/excel/`。

- [ ] 选取一个公开 XLSX fixture，冻结明确的输入、预期值、目标单元格和源文件哈希；源文件保持不变。
- [ ] 由已确认的非 Ollama provider 生成实际 Office 成品；若 provider 无法调用，记录失败并停止模型闭环结论。
- [ ] 经 Harness 保存 artifact、格式/结构/公式/数值格式检查、artifact-v1 评分、`score.json`、`issues.json` 和可读报告。
- [ ] 核对 issue 是否包含 sheet/cell、actual、expected 和可执行修复建议。
- [ ] 仅让候选修改一个 allowlist 内的 skill 字段，保存原始 provider 记录与 candidate diff。
- [ ] 实际运行 `CandidateVerifier`、候选复评、regression/hidden/OOD 晋级门禁与 `PromotionController`，保存 round summary 和 checkpoint。
- [ ] 必需视觉/语义通道不可用时标记 incomplete，不补造总分，也不允许通过完整评估门禁。

**验收：** baseline 与 candidate 均有成对真实 artifact、score、issues、verifier、split 指标和 gate 决定；结果可从保存文件复核。provider 阻断时阶段标为 `blocked` 并附具体错误。

## 阶段 3：三域 Harness 与 evaluator 覆盖

**检查范围：** `src/workagent_rsi/harness.py`、`run.py`、`harness_artifact_evaluator.py`、`artifact_assessment.py`、`office_checks.py`、`tests/test_artifact_assessment_excel.py` 和 `tests/test_office_evaluator.py`。
**结果目录：** `project_artifacts/results/qualification/three-domain-artifact-assessment-20261011/`。

- [ ] 用同一简洁 Harness 入口，依次运行 Excel、Word、PowerPoint；每个域先单任务，核对后再扩代表性案例。
- [ ] Excel 核验 OOXML、sheet、cell、公式文本、可验证的计算值、数值格式和图表引用。
- [ ] Word 核验 OOXML、段落、标题层级、表格单元格和要求内容。
- [ ] PowerPoint 核验 OOXML、页数、对象文本、边界、几何重叠和可访问的图表数据。
- [ ] 分开记录 semantic、visual renderer、COM reopen 与 package/check 通道状态；不可用能力记作 assessment gap。
- [ ] 每域保存输入/输出哈希、result、`assessment.json`、`score.json`、`issues.json` 和可读报告。

**验收：** 三域均有实物文件、Harness 结果、artifact-v1 score/issues、通道状态和正反例；只有视觉及语义实际完成后，才声明内容准确性与页面可读性也完成端到端验证。

## 阶段 4：RSI 三域串行扩展

**检查范围：** `src/workagent_rsi/workagent_experiment.py`、`workagent_evaluator.py`、`rsi_loop.py`、`rsi_feedback.py`、`tests/test_rsi_artifact_feedback.py`。
**结果目录：** `project_artifacts/results/rsi-live-20261011/three-domain/`。

- [ ] 冻结非空 `develop`、`regression`、`hidden`、`ood_transfer` split 及其任务/spec hash。
- [ ] 串行运行 baseline，产生一个候选；不并行开展实验。
- [ ] 对候选逐项执行并记录 allowlist、leakage、schema、compile、tests、artifact execution config 检查。
- [ ] 串行评估全部 split；隐藏任务级结果不进入反馈，只用于冻结门禁聚合。
- [ ] 应用现有阈值：`quality_gain=0.05`、`success_tolerance=0.01`、`protected_quality_tolerance=0.01` 和 evaluation-time budget。
- [ ] 保存 score/issues、candidate diff、provider record、round cost、晋级 gate、checkpoint 和人工可读报告。

**验收：** 至少一轮完整 RSI；所有 split assessment complete、重复评分一致、verifier 通过，晋级理由逐门可见。若拒绝，champion 不得变化。当前聊天助手只能记作人工候选来源，不能冒充程序内 provider。

## 阶段 5：复核与结论

**更新范围：** `project_artifacts/execution_log.md`、`project_artifacts/execution_plan.md`。
**产物：** `project_artifacts/formal_study/stage6_three_domain_rsi_manifest.json`。

- [ ] 逐项复读结果，核对输入/输出哈希、manifest、score、issues 和 round summary。
- [ ] 对照验收标准标记 `completed`、`incomplete` 或 `blocked`，附实际证据路径。
- [ ] 运行相关完整测试、compileall、git diff check；不以旧分支的历史报告代替当前分支验证。
- [ ] 区分工程资格、模型 provider 运行和外部 benchmark 结论。

**验收：** manifest 与实际磁盘结果一致，限制清晰可查；只报告本轮刚验证的结果。
