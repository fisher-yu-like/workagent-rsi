# 将远端 ArtifactEvaluator 和 ArtifactVerifier 接入现有 WorkAgent Harness

> 状态：已完成。实现提交 `654b3f59cf740f20e83a3c5149030e3e59cbe0ba` 已推送到 `origin/codex/merge-office-artifact-assessment`。

**目标：** 保留当前 WorkAgent Harness 的单入口和任务运行方式，用远端 evaluator 评估 Office 成品，并用远端 verifier 输出可供 RSI 使用的结构化问题报告。

**方案：** 新分支继续以远端评估分支为基线，只接入运行现有 WorkAgent 所需的代码和最小适配。Harness 仍通过 `Harness.run(task)` 启动；Office 成品只创建一份远端 `SharedAssessment`，再由远端 `ArtifactEvaluator` 和 `ArtifactVerifier` 顺序处理。

**关键模块：** `AcceptanceSpec`、`SharedAssessment`、`ArtifactEvaluator`、`ArtifactVerifier`、当前 WorkAgent provider、现有 `Run` / `Orchestrator`。

**依据：** 用户关于以远端为准、顺序推进、保留简单 Harness，并优先采用“将远端 evaluator 和 verifier 接入当前 Harness”的要求。

---

## 当前基线

| 内容 | 基线 |
|---|---|
| 权威代码 | `origin/feat/office-artifact-dual-assessment`，提交 `3b1c1840d18a89346319600b250226ebfc822354` |
| WorkAgent 来源 | `codex/closed-loop-rsi`，提交 `bd729791c5377d8c4e7e2ef155eff5f67524ea87` |
| 集成分支 | `codex/merge-office-artifact-assessment`，从权威代码创建 |
| 工作目录 | `worktrees/office-artifact-assessment-merge/` |

当前本地 `Run` 为每种 Office provider 选择 `OfficeArtifactEvaluator`，并通过 `Orchestrator` 调用 `evaluate(task, artifacts, trace_id)`。远端的 `ArtifactEvaluator` 与 `ArtifactVerifier` 接收同一份 `Assessment`；创建该 `Assessment` 需要 `AcceptanceSpec` 和 `SharedAssessment`。因此需要一层薄适配，把现有 Harness 的调用协议接到远端评估链上。

## 集成边界

- 保留 `Harness.run(task)`、当前 WorkAgent provider、Office 文件生成、单一运行目录和现有 COM 重开检查。
- 接入当前 WorkAgent 运行所需的 `workagent_provider.py`、`workagent_office.py`、`artifact_com.py`、响应 schema 和提示文件；仅为接入修改 `harness.py`、`run.py` 及必要的结果适配。
- 以远端的 `assessment_contracts.py`、`artifact_assessment.py`、`artifact_evaluator.py`、`artifact_verifier.py` 和它们需要的语义/视觉支持模块为准；不复制或维护第二套 Office 评分逻辑。
- 本地 `CandidateVerifier` 继续验证 RSI 候选补丁的路径、内容和执行安全。远端 `ArtifactVerifier` 新增到成品评估链，负责成品缺陷定位和修复建议。
- 保留现有 Harness 和 RSI 运行入口；不重写候选生成或晋级流程。将 `ScoreReport` 和 `IssueReport` 写入同一运行结果目录，供当前结果消费者和 RSI 后续使用。
- 所有实现按下方顺序逐项完成；当前步骤完成后再进入下一步。

## 评估行为

1. 任务显式提供 `acceptance_spec` 时，使用其中的要求、证据位置、维度和 `dimension_weights`。三类维度分别覆盖数值/公式/格式等客观正确性、内容语义、视觉版式；具体名称沿用任务规格。
2. 没有 `acceptance_spec` 时，使用远端 `spec_from_task` 转换现有 `expected_constraints`。这类旧任务默认只评分确定性正确性，不自动推断语义或视觉要求。
3. 语义和视觉要求必须在规格中有明确的检查标准；语义/视觉通道使用远端 `ModelReviewConfig` 配置 Codex 或 API，视觉通道还需要远端 renderer。必需通道缺失、失败或证据不足时，状态为未完成，不能当作通过。
4. 同一份 `Assessment` 同时交给 evaluator 和 verifier。评分以远端 `ScoreReport.total_score`（0–100）为准。为兼容当前 `EvaluationReport.score` 消费者，Harness 的兼容字段保留 0–1 表示，等于总分除以 100；未完成时为 `null`。不调用旧 `OfficeArtifactEvaluator` 产生第二份分数。
5. `IssueReport` 保留 requirement ID、精确位置、实际值、期望值、证据引用、严重级别和修复建议。单产物任务可将唯一产物映射到唯一规格项；多产物任务中，`AcceptanceSpec.artifacts` 的键必须与 WorkAgent 清单中的完整相对路径（如 `outputs/summary.xlsx`）一致，且产物不能多报或漏报。映射不完整或歧义时报告未完成，不静默挑选文件。

## 顺序实施步骤

### 第一步：接入现有 WorkAgent 运行能力

将当前 WorkAgent provider、Office adapter、COM 检查、响应 schema 和提示文件接入远端基线。更新现有 Harness/Run 内部 provider 组装，让调用仍保持 `Harness.run(task)`。保留运行目录和 COM 检查行为。

### 第二步：接入远端共享评估链

新增一层薄适配，满足当前 `Orchestrator` evaluator 接口。将 `TaskSpec` 转换为远端 `AcceptanceSpec`，把生成的 Office 产物映射到 spec 中声明的产物名，再调用一次 `SharedAssessment.inspect`。随后将同一个 `Assessment` 依次交给远端 `ArtifactEvaluator.evaluate` 和 `ArtifactVerifier.verify`。

### 第三步：把报告写入当前运行结果

将远端 assessment、score、issues 和人类可读 report 写入当前 Harness 的结果目录；在 `result.json` 中保留现有状态与评估摘要，并引用完整结构化报告。Office provider 的结果由远端 `ScoreReport` 决定通过状态；非 Office 的 `BasicEvaluator` 继续处理原有 smoke 任务。

### 第四步：保持 RSI 结果可用

更新 `WorkAgentFrozenEvaluator` 和 `WorkAgentExperimentRunner` 使用远端评估身份，避免继续校验旧 `OfficeArtifactEvaluator` 的 hash。每个 WorkAgent 评估行保留 `score_report` 和 `issue_report`，让开发任务中的位置、实际/期望差异和修复建议能进入 RSI 结果记录。让现有远端 artifact-v1 RSI 环路接受 `WorkAgentSkill.instructions` 的受限补丁，并继续由 `CandidateVerifier` 检查候选安全、由原候选晋级入口作决定；RSI 兼容分数仍使用 0–1，评分报告保留 0–100。

### 第五步：审阅、提交和推送

更新面向普通使用者的配置说明，示例继续从 `Harness.run(task)` 开始，并说明 `acceptance_spec`、模型配置和视觉渲染的要求。审阅最终差异，仅保留 WorkAgent 运行接入、远端评估链适配、结果报告和必要文档；随后提交并推送 `codex/merge-office-artifact-assessment`。

## 完成标准

- 集成分支保留远端评估代码作为权威实现，且新分支基于远端提交 `3b1c184`。
- 普通调用仍只有 `Harness.run(task)` 这一个直观入口；WorkAgent Office 产物只经过一条评估链。
- evaluator 和 verifier 读取同一份证据绑定 `Assessment`；无本地重复评分路径。
- 可确定性要求、语义判断和视觉判断按任务规格及有效权重评分；不可用的必需评审通道不会被视为通过。
- 结构化问题报告包含具体位置、实际/期望差异、证据和修复建议，并保存在 Harness 结果目录中。
- RSI 的候选补丁安全校验仍由本地 `CandidateVerifier` 负责；WorkAgent 评估记录同时包含远端评分和问题报告。
- 新分支提交并推送到远端仓库。

## 审批边界

用户已批准按此计划执行。已人工审阅差异，并提交、推送 `codex/merge-office-artifact-assessment`。

## 执行进度

- [x] 第一步：接入现有 WorkAgent 运行能力。
- [x] 第二步：接入远端共享评估链。
- [x] 第三步：把报告写入当前运行结果。
- [x] 第四步：保持 RSI 结果可用。
- [x] 第五步：审阅、提交和推送。

## 验证与交付记录

- 验证工作目录：`C:\Users\sy\Desktop\workagent-rsi\worktrees\office-artifact-assessment-merge`
- 验证时间：2026-10-08 19:21:43 至 19:21:46（Asia/Shanghai）
- 代码基线：`3b1c1840d18a89346319600b250226ebfc822354`
- Python：`3.12.10`
- `git diff --check HEAD^ HEAD`：退出码 0，无空白错误。
- `py -3.12 -m compileall -q src/workagent_rsi`：退出码 0，无输出。
- 未运行测试、WorkAgent 或 Office 任务；没有生成或声称任何任务评估结果。
- 实现提交：`654b3f59cf740f20e83a3c5149030e3e59cbe0ba`；推送命令成功，远端分支已创建。
