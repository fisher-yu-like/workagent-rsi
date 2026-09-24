# WorkAgent-RSI 项目整体介绍

## 1. 项目定位

WorkAgent-RSI 是一个面向 Excel、Word 和 PowerPoint 办公任务的、基准驱动的递归技能改进框架。这里的 RSI 指 Recursive Skill Improvement，即在固定任务、验证器、评估器和晋级政策约束下改进 Prompt、工具策略、上下文、Office 脚本和候选测试，而不是让模型不受限制地修改自身权重、目标或评估标准。

项目的核心原则是：候选生成器可以提出修改，独立 verifier 决定候选是否安全可执行，冻结 evaluator 判断候选是否真的变好，promotion controller 决定是否注册为新 champion，registry 保留不可变版本并支持 rollback。

本仓库已完成 Harness、Office 资格验证、Codex-backed candidate provider、闭环 RSI 基础设施和 E01-E12 的 30-task pilot。结果不能解释为正式主研究、外部 WorkAgent 产品性能或通用 Office 能力。

## 2. 研究基础

项目最初调研的两篇参考工作保存在 docs/literature_review.md 和 docs/sources/。Phase 2 将参考思想落实为以下工程约束：

- 候选提出、验证、评估和晋级权力分离；
- 候选只能进行有预算的原子编辑；
- hidden/OOD 结果不得向候选生成器泄漏任务级信息；
- evaluator、hidden tests、promotion policy、allowlist 和历史证据属于保护区；
- 每个接受或拒绝决策必须指向真实 trace、artifact、hash 和 evaluator 输出；
- 缺失能力保持 failed、unavailable 或 blocked，不补造分数。

## 3. 当前架构

~~~mermaid
flowchart TB
  DATA[Versioned Pilot Dataset] --> RUN[Benchmark and Experiment Runner]
  REG[Immutable Skill Registry] --> EXEC[Skill-Aware Office Executor]
  RUN --> EXEC
  EXEC --> TRACE[SQLite Trace Memory]
  EXEC --> ART[Content-Addressed Artifact Store]
  TRACE --> DIAG[Deterministic Failure Diagnoser]
  ART --> DIAG
  DIAG --> PROVIDER[Codex CLI Candidate Provider]
  REG --> PROVIDER
  PROVIDER --> WS[Isolated Candidate Workspace]
  WS --> LEAK[Leakage Critic]
  LEAK --> VERIFY[Fail-Closed Verifier]
  VERIFY --> FROZEN[Frozen Artifact Evaluator]
  FROZEN --> PROMOTE[Promotion Controller]
  PROMOTE --> REG
  REG --> ROLLBACK[Rollback Manager]
  FROZEN --> REPORT[E01-E12 Evidence]
~~~

### 3.1 已实现组件和真实地址

| 组件 | 地址 | 当前作用 |
|---|---|---|
| 基础任务与 artifact 契约 | src/workagent_rsi/contracts.py | TaskSpec、SkillManifest、ArtifactRef、EvaluationReport |
| RSI 证据契约 | src/workagent_rsi/rsi_contracts.py | CandidatePatch、FailureDiagnosis、VerificationReport、SkillVersion、PromotionDecision、EvaluationContract、ExperimentResult |
| Harness orchestrator | src/workagent_rsi/orchestrator.py | 运行状态、重试、artifact ingestion、evaluator 调用 |
| Mock/Office adapters | src/workagent_rsi/executor.py | Mock Harness 与本地真实 OOXML 资格验证 |
| Skill-aware Office runtime | src/workagent_rsi/skill_runtime.py | 根据版本化 marker policy 生成真实 XLSX、DOCX、PPTX |
| 确定性故障诊断 | src/workagent_rsi/diagnosis.py | 从公开失败证据分类 input/planning/tool/format/semantic/visual/evaluator/safety |
| 候选隔离 | src/workagent_rsi/candidate_workspace.py | allowlist 复制、保护文件排除、独立 Git、候选 AGENTS 规则 |
| Candidate provider | src/workagent_rsi/candidate_provider.py | Codex CLI/Ollama 或 deterministic test provider，结构化 CandidatePatch 输出 |
| 泄漏检查 | src/workagent_rsi/leakage.py | 保护值、task-specific map、evaluator/governance 路径和越权能力检查 |
| Verifier | src/workagent_rsi/verifier.py | path policy、leakage、patch JSON、compile、candidate tests，fail-closed |
| Frozen evaluator | src/workagent_rsi/frozen_evaluator.py | split/evaluator hash 校验、真实 Office artifact 评价、hidden 行级结果隐藏、自动 response judge |
| Registry/Rollback | src/workagent_rsi/registry.py | 内容寻址 skill package、SQLite 版本索引、champion alias、lineage、rollback |
| Promotion | src/workagent_rsi/promotion.py | develop、regression、hidden、OOD、安全、复现、成本非补偿式门禁 |
| RSI loop | src/workagent_rsi/rsi_loop.py | diagnosis→provider→verify→evaluate→promote→registry |
| Experiment runner | src/workagent_rsi/experiment_runner.py | E01-E12 immutable invocation 和 comparator replay |
| 命令入口 | project_artifacts/phase3_experiments/scripts/run_e01_e12.py | 运行指定或全部实验 |

## 4. Skill 如何表示和工作

Pilot skill 是一个不可变的版本化 JSON package。当前最小技能参数是 marker_source：

- task_id：baseline 行为，将任务 ID 写入 artifact；
- required_text：candidate 行为，将任务要求的标记写入 artifact。

Baseline 的 task_id 策略是故意设置的可观察缺陷，用于验证闭环能否从真实 Office 失败中诊断、生成候选、验证并晋级。它不是生产 Office agent 的质量基线。

SkillVersion 保存 skill_id、version、parent_version、content_hash、manifest_hash、candidate_id、status、evidence_refs 和 created_at。Skill package 存入 registry/packages/<content_hash>/，历史版本不能覆盖；champion 只是 SQLite 中可移动的 alias。Rollback 只移动 alias，不删除版本和历史证据。

CandidatePatch 由一个或多个 AtomicEdit 构成。每个 edit 必须包含 target_path、component、hypothesis、expected_metric 和 patch。当前 pilot 将可编辑目标限制为 skill.json，模型的 patch 字段必须是精确 JSON 对象。

## 5. Candidate provider

真实 candidate provider 使用：

- Codex CLI 0.144.2；
- Codex 的 ephemeral、workspace-write、JSONL 和 output-schema 模式；
- 本机 Ollama provider；
- qwen2.5:7b 模型。

运行目录是新建的独立 candidate workspace，不是主仓库。Workspace 仅包含 champion skill.json、公开 diagnosis、候选规则和 AGENTS.md；不包含 hidden tasks、evaluator、promotion policy、registry history 或项目复制的凭据。

远程 provider 路径在资格探测中出现过配置环境变量缺失和网络超时，均保留为失败证据。Ollama provider 成功返回真实 token usage 和结构化输出。第一条本地候选因 patch 尾随引号被 verifier 拒绝；收紧 provider 合约后候选通过。这些失败没有被删除或改写成成功。

## 6. 执行 Pipeline

### 6.1 单轮 RSI

1. 从 registry 读取 champion。
2. 在 develop/evolve 等允许 split 上生成真实 Office artifacts。
3. Frozen evaluator 重新打开 artifact 并输出任务级失败。
4. FailureDiagnoser 生成带证据 hash 的诊断。
5. CandidateWorkspaceBuilder 导出受限候选目录。
6. Codex provider 返回 schema-valid CandidatePatch。
7. LeakageCritic 与 CandidateVerifier 执行保护路径、泄漏、JSON、compile 和测试门禁。
8. 通过的 candidate 应用到新的 skill package。
9. 在 develop、regression、hidden、OOD 上重新生成真实 artifacts。
10. PromotionController 执行非补偿式门禁。
11. 接受的版本注册并移动 champion alias；拒绝版本保留证据。
12. Rollback 可将 alias 移回任一已接受父版本。

### 6.2 Hidden 数据隔离

Hidden split 文件位于 project_artifacts/phase3_experiments/data/protected/。候选 workspace 不复制这些文件。FrozenEvaluator 在 hidden split 上保存受保护的完整结果，但公开 report 只返回 task_count、success_count、score、split hash 和 evaluator hash，不返回行级任务内容。

## 7. 数据与基础资格验证

Pilot 数据集版本为 synthetic-office-taskset-v0.1.0：

- 30 个 project-generated 任务；
- Excel、Word、PowerPoint 各 10 个；
- evolve 12、develop 6、regression 4、hidden 5、OOD 3；
- public 25、protected 5；
- 14 项数据质量检查全部通过。

基础 Harness 回归：

- Mock B0：25/25 succeeded，mean score 1.0；
- Local Office B0：25/25 succeeded，mean score 1.0；
- Word/Excel/PowerPoint COM：25/25 打开成功，版本均为 16.0。

Mock B0 和 Local Office B0 是资格验证，不是 RSI 实验结果。

## 8. E01-E12 Pilot 结果

最终索引位于 project_artifacts/phase3_experiments/results/e01_e12/latest_summary.json 和 latest_summary.md。每个实验保留独立 contract、provider logs、candidate、verification、真实 Office artifacts、evaluation、registry 和 decision。

| 实验 | 最新 Pilot 结果 | 解释 |
|---|---|---|
| E01 | fixed baseline task success 0.0 | 故意有缺陷的 task_id marker baseline |
| E02 | develop 0.0→1.0；regression/hidden/OOD delta 1.0 | Self-Refine 候选通过 verifier 和 promotion |
| E03 | generator-only accept 1.0；verified accept 1.0；invalid promotion 0.0 | 同一真实候选的 paired policy replay |
| E04 | develop-only accept 1.0；modular accept 1.0；invalid promotion 0.0 | 当前候选未触发额外 evaluator 拒绝 |
| E05 | develop 0.0→1.0；critical regressions 0 | 完整闭环成功晋级 |
| E06 | verifier enabled pass 1.0；disabled accept 1.0；prevented 0.0 | 当前干净候选两种政策一致 |
| E07 | automated agreement rate 0.0 | response judge 只看指令而 artifact evaluator 发现真实文件缺标记；无人工标注声明 |
| E08 | domain-specific OOD 0.0；shared OOD 1.0；transfer delta 1.0 | shared marker policy 在 OOD Office artifact 上通过 |
| E09 | edit count 1；regularized/unregularized admissible 均 1.0 | 候选本身满足单原子编辑预算 |
| E10 | regularized/unregularized accept 均 1.0；prevented 0.0 | 所有保护门禁均通过 |
| E11 | critic enabled rejection 1.0；disabled rejection 0.0 | task-specific answer map 被 leakage critic 拦截 |
| E12 | Word/PPT develop 0.0→1.0；protected deltas 1.0 | Word/PPT 闭环真实 artifact 验证通过 |

这些数值是为闭环机制构造的 pilot，任务和 skill 变化高度受控，不能解释为自然分布中的模型能力提升，也不能用于正式统计显著性或产品比较。

## 9. E07 自动交叉评估

用户明确要求不使用人工标注，因此 E07 改为两个自动通道：

- Artifact evaluator：真实重新打开 DOCX/XLSX/PPTX 并检查要求标记；
- Response judge：只根据任务指令文本做自动判断。

E07 agreement rate 为 0.0，说明 response-only 评价在本 pilot 中会把“指令包含要求”误认为“最终文件包含要求”。该结果支持 artifact-level evaluator 的必要性，但不是 evaluator-human agreement。

## 10. 安全与可信边界

- Candidate 不能写主仓库。
- Candidate workspace 不包含 hidden/evaluator/governance 文件。
- 相对路径、Windows 保留名、路径穿越和 symlink 受到限制。
- Provider 输出必须通过 JSON schema 和 Pydantic contract。
- evaluator、promotion、registry 历史和 allowlist 不可由候选修改。
- safety、leakage、critical regression、hidden/OOD、reproducibility 和 cost gate 不能互相补偿。
- 失败 provider 输出、无效 patch 和被拒候选继续保留。
- 实验 invocation 不覆盖旧目录。

## 11. 测试与复现

所有测试均位于单一顶层 tests/ 目录。

~~~powershell
py -3.12 -m pip install -e .
py -3.12 -m pytest -q --basetemp="$env:TEMP\workagent-rsi-tests"
py -3.12 project_artifacts/phase3_experiments/data/quality_check.py
py -3.12 project_artifacts/phase3_experiments/scripts/run_b0_qualification.py
py -3.12 project_artifacts/phase3_experiments/scripts/run_b0_office_qualification.py
powershell -ExecutionPolicy Bypass -File project_artifacts/phase3_experiments/scripts/verify_office_com.ps1 -Root project_artifacts/phase3_experiments/results/b0_office_qualification -OutputJson project_artifacts/phase3_experiments/results/b0_office_qualification/com_validation.json
py -3.12 project_artifacts/phase3_experiments/scripts/run_e01_e12.py --provider codex --codex-backend ollama --local-model qwen2.5:7b
~~~

## 12. 已知限制与下一步

- 数据集只有 30 个合成 pilot 任务，不能支持主研究结论。
- 当前 skill 只控制 marker policy，尚未覆盖复杂公式、模板迁移、布局优化和视觉生成。
- qwen2.5:7b 的本地模型 metadata 在 Codex CLI 中使用 fallback metadata，可能影响 token/上下文估计。
- E03/E04/E06/E09/E10 的 comparator 使用同一真实候选进行 paired policy replay，隔离政策影响，但没有执行独立候选搜索轨迹。
- Frozen evaluator 当前聚焦格式和 required marker，尚未包含完整公式重算、Word 分页、PPT 重叠和视觉 judge。
- 远程 provider 网络路径不稳定，本次最终候选证据来自本地 Ollama。
- 正式主研究仍需要扩展到至少 90 个独立来源/模板任务、更多 seeds、视觉人工校准样本以及第二个 executor/model。

## 13. 主要证据入口

- 设计规格：docs/superpowers/specs/2026-09-24-workagent-rsi-closed-loop-design.md
- 实施计划：docs/superpowers/plans/2026-09-24-workagent-rsi-closed-loop.md
- 数据质量：project_artifacts/phase3_experiments/data/quality_report.json
- Mock B0：project_artifacts/phase3_experiments/results/b0_qualification/summary.json
- Office B0：project_artifacts/phase3_experiments/results/b0_office_qualification/summary.json
- Office COM：project_artifacts/phase3_experiments/results/b0_office_qualification/com_validation.json
- E01-E12 总索引：project_artifacts/phase3_experiments/results/e01_e12/latest_summary.json
- 单实验完整证据：project_artifacts/phase3_experiments/results/e01_e12/Exx/<invocation>/
