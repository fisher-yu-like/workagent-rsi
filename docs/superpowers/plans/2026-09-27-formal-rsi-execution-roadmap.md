# WorkAgent-RSI 正式研究执行方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 每一阶段完成后必须执行验证并等待对应 Gate；不得把未运行内容写成实验结果。

**目标：** 在当前可运行的简化 Harness 和一轮 RSI pilot 基础上，建立可复现的真实 Office 执行、文件级自动评估、多轮递归技能改进、外部数据实验和论文级证据链。

**架构：** 保留对外的 `Harness`、`Run`、`Learn`、`Check`、`Store` 五个简单名称；内部继续分离执行器、候选生成器、验证器、冻结评估器、版本注册和晋级门禁。普通单轮保持“直接执行正常任务”，不再人为制造错误；只有研究实验才启动 RSI 闭环。所有运行输出统一写入 `project_artifacts/results/`，历史 phase 目录只读保留。

**技术栈：** Python 3.12、Pydantic 2、SQLite、pytest、openpyxl、python-docx、python-pptx、LibreOffice 或 Windows Office COM（按能力门禁选择）、Codex CLI/Ollama 或声明式远程 provider、Git。

**依据：** `docs/literature_review.md`、`docs/superpowers/specs/2026-09-24-workagent-rsi-closed-loop-design.md`、`Codex三阶段项目执行计划.md`、RRSI（arXiv:2609.24972）和 Genuine RSI（arXiv:2609.11873）。

## 全局约束

- 当前基线为 commit `59987d4`，现有测试必须保持通过；不得覆盖历史结果。
- 所有新运行结果必须位于 `project_artifacts/results/<category>/<invocation>/`。
- 测试文件只放在顶层 `tests/`，不创建 phase-specific 测试目录。
- 普通单轮不调用大模型；候选生成 provider 与任务执行 provider 必须分离并分别记录。
- candidate workspace 不能包含 hidden 数据、评估器、晋级策略、凭据或历史证据。
- evaluator 只读、带 hash、与候选技能解耦；`unavailable` 不得转换成分数。
- 主研究不使用人工标注；主要分数来自格式、结构、公式、OOXML、渲染几何和固定自动 VLM（若可用）检查。
- 所有正式结论必须同时给出数据版本、代码 commit、配置 hash、evaluator hash、随机种子和原始结果路径。
- 每个阶段结束时单独提交 Git commit；不得在未通过 Gate 时进入下一阶段。
- 任何外部数据先审查官方来源和许可证，许可证不清晰时只做适配器设计，不下载进正式数据目录。

## 当前基线与不重复事项

- 简化公共 API 已完成：`src/workagent_rsi/harness.py`、`run.py`、`learn.py`、`check.py`、`store.py`。
- 本地 Office 适配器、文件重开评估器、候选隔离、Codex/Ollama provider、泄漏检查、冻结 split、版本注册和一轮 `RSILoop` 已完成。
- 当前测试基线为 `61 passed`。
- 当前 30 条任务是项目自生成 pilot；E01/E05 只证明工程闭环可运行，不是外部 benchmark 或论文主结果。
- 不重新实现已完成的 Phase 1/2 设计，不修改 `phase1_harness/results/` 和旧 `phase3_experiments/results/`。

## 阶段总览与审批点

| 阶段 | 交付目标 | 主要 Gate | 通过后动作 |
|---|---|---|---|
| 0 | 基线、实验合约和能力清单冻结 | G0 | 请求批准真实执行器开发 |
| 1 | 真实 Office 执行器 provider | G1 | 请求批准文件级 evaluator 开发 |
| 2 | 三域自动文件评估器 | G2 | 请求批准多轮 RSI 开发 |
| 3 | 六轮 RSI、checkpoint、resume、成本和负证据 | G3 | 请求批准外部数据接入 |
| 4 | 外部数据适配、许可和质量门禁 | G4 | 请求批准小规模正式 pilot |
| 5 | baseline、消融、迁移和稳定性 pilot | G5 | 请求批准正式主实验 |
| 6 | 正式实验、统计、报告和 GitHub 交付 | G6/G7 | 发布论文级结果包 |

默认策略是每个 Gate 都等待用户批准；用户可以一次性批准整套方案，但任何阶段失败仍会停止并报告原因。

---

## 阶段 0：基线冻结与正式实验合约

### 目标

把当前 pilot 和未来正式研究严格分开，建立不可变的运行身份、能力矩阵、成本字段和结果目录规则。

### 文件

- 创建：`project_artifacts/formal_study/contract.json`
- 创建：`project_artifacts/formal_study/capability_matrix.json`
- 创建：`project_artifacts/formal_study/baseline_manifest.json`
- 创建：`project_artifacts/formal_study/README.md`
- 修改：`project_artifacts/execution_plan.md`
- 修改：`project_artifacts/artifact_manifest.md`
- 修改：`Agent.md`
- 测试：现有 `tests/` 全量回归，不新增功能测试文件

### 实施步骤

- [ ] 记录 `git rev-parse HEAD`、Python、依赖、Codex CLI、Ollama、Office/LibreOffice 能力和操作系统信息。
- [ ] 运行 `py -3.12 -m pytest -q --basetemp="$env:TEMP\\workagent-rsi-baseline"`。
- [ ] 运行 `py -3.12 -m compileall -q src tests project_artifacts/phase3_experiments/scripts`。
- [ ] 运行数据质量检查并保存命令、退出码和输出 hash。
- [ ] 定义正式实验 contract：数据 fingerprint、split、evaluator 版本、模型/provider、最大轮数、编辑预算、超时、成本上限和随机种子。
- [ ] 为每个能力写明 `available`、`unavailable` 或 `not_claimed`；缺失 Office/模型能力时禁止静默降级。
- [ ] 将历史 E01/E05 归类为 `pilot_mechanism_validation`，禁止在正式报告中混称。

### G0 验收

- 测试、编译和数据质量检查全部通过。
- 正式 contract 可解析并具有唯一 hash。
- 能力矩阵明确区分本地 Python、LibreOffice、COM、GUI 和 Codex provider。
- `project_artifacts/results/` 目录规则和历史证据边界写入文档。
- 结果中没有“已完成正式实验”的错误表述。

### G0 停止条件

测试失败、数据 split hash 漂移、关键依赖版本无法记录、或无法确认外部数据许可时停止，不进入阶段 1。

---

## 阶段 1：真实 Office 执行器 provider

### 目标

把当前确定性本地适配器保留为 smoke provider，同时增加可检测、可记录、失败关闭的真实 Office 执行路径。真实路径必须产生可由 Office/LibreOffice 重新打开的文件，不得用文本改扩展名。

### 文件

- 修改：`src/workagent_rsi/executor.py`
- 修改：`src/workagent_rsi/skill_runtime.py`
- 修改：`src/workagent_rsi/run.py`
- 修改：`src/workagent_rsi/contracts.py`
- 创建：`src/workagent_rsi/office_capabilities.py`
- 创建：`project_artifacts/phase3_experiments/scripts/check_office_capabilities.py`
- 创建：`tests/test_real_office_executor.py`
- 修改：`tests/test_pipeline_e2e.py`
- 修改：`project_artifacts/phase3_experiments/scripts/run_b0_office_qualification.py`

### 接口约束

```python
class OfficeProvider(Protocol):
    def capability(self) -> CapabilityReport: ...
    def execute(self, task: TaskSpec, skill_id: str, output_root: Path) -> Iterable[dict]: ...
```

`Run` 通过配置选择 `smoke`、`local_office`、`libreoffice` 或 `com`；默认仍为当前正常单轮路径，不改变用户现有调用。

### 实施步骤

- [ ] 先为 provider 选择、能力探测、不可用状态和版本记录写失败测试。
- [ ] 实现能力探测：Office 应用版本、LibreOffice 版本、COM 可连接性、进程清理能力和临时目录权限。
- [ ] 将现有 Python 生成器包装成显式 `local_office` provider，保留为可重复 smoke/qualification provider。
- [ ] 接入至少一个真实重开路径：优先 Windows Office COM；若 COM 不可用，接入 LibreOffice headless 并把缺失能力标为 unavailable。
- [ ] 将 provider、应用版本、命令、退出码、耗时、artifact hash 和 stderr 写入 trace。
- [ ] 对 Excel、Word、PowerPoint 各完成一个最小真实文件重开测试。
- [ ] 确保超时或 Office 进程残留时运行标记为失败，并在 finally 阶段清理进程。
- [ ] 运行本阶段 qualification，结果写入 `project_artifacts/results/qualification/real-office/`。

### G1 验收

- 三种 Office 文件都能生成、重新打开并读取。
- provider 不可用时返回 `unavailable`，不伪造成功分数。
- 任务执行 provider 和候选生成 provider 的记录可分离追踪。
- 至少 25 个公开 qualification 任务完成，成功率按真实 evaluator 输出统计。
- 没有未关闭的 Office 进程，所有命令和日志可复现。

### G1 停止条件

任一文件类型无法真实重开、artifact hash 缺失、provider 将不可用转成成功，或 COM/LibreOffice 产生不可追踪的残留进程时停止。

---

## 阶段 2：Office 文件级自动评估器

### 目标

将当前 `required_text` marker 检查升级为三域文件级评估。主研究不依赖人工标注；自动 evaluator 必须先硬检查，再执行结构和渲染检查。

### 文件

- 修改：`src/workagent_rsi/evaluator.py`
- 修改：`src/workagent_rsi/frozen_evaluator.py`
- 创建：`src/workagent_rsi/office_checks.py`
- 创建：`src/workagent_rsi/render_checks.py`
- 创建：`tests/test_office_quality.py`
- 修改：`tests/test_office_evaluator.py`
- 创建：`project_artifacts/phase3_experiments/configs/evaluator_v2.json`
- 创建：`project_artifacts/phase3_experiments/scripts/validate_evaluator.py`

### 评估层级

- [ ] 格式层：ZIP/OOXML 可读、媒体类型、文件完整性、无损坏。
- [ ] Excel：工作表、单元格、公式、公式计算结果、错误值、合并单元格、行列结构和关键格式。
- [ ] Word：段落、表格、标题层级、样式、页数、页面溢出和渲染可读性。
- [ ] PowerPoint：页数、文本和占位符、对象边界、重叠、溢出、空白页和渲染可读性。
- [ ] 将每项检查产出结构化 evidence，而非只输出总分。
- [ ] evaluator 版本和源码 hash 写入每个报告；冻结评估拒绝 hash 不一致的运行。
- [ ] 可选固定 VLM 只作为自动语义/视觉补充，记录模型、帧 hash、调用次数和 unavailable 状态；不使用人工标注。
- [ ] 为 evaluator 增加 adversarial fixture，确认候选无法修改评估器或隐藏任务。

### G2 验收

- 每个领域都有格式、结构和至少一项渲染/几何自动检查。
- evaluator 能区分执行失败、格式失败、结构失败、渲染失败和语义失败。
- hidden split 只返回聚合结果，candidate workspace 不含 hidden 文件。
- evaluator 版本漂移会被 contract 拒绝。
- 自动质量报告能解释每个失败任务，不依赖人工分数。

---

## 阶段 3：多轮 RSI 与证据闭环

### 目标

将当前 `RSILoop.run_round()` 扩展为可恢复的六轮 RSI，体现 RRSI 的编辑预算、泄漏筛查、负证据、成本门禁和 protected split，同时满足 Genuine RSI 对持久经验和后续继承性的要求。

### 文件

- 修改：`src/workagent_rsi/rsi_loop.py`
- 修改：`src/workagent_rsi/experiment_runner.py`
- 修改：`src/workagent_rsi/candidate_provider.py`
- 修改：`src/workagent_rsi/rsi_contracts.py`
- 修改：`src/workagent_rsi/registry.py`
- 修改：`src/workagent_rsi/promotion.py`
- 创建：`src/workagent_rsi/costs.py`
- 创建：`tests/test_multiround_rsi.py`
- 修改：`tests/test_rsi_loop.py`
- 修改：`tests/test_experiment_runner.py`
- 修改：`project_artifacts/phase3_experiments/scripts/run_e01_e12.py`

### 运行协议

- [ ] 新增 `RSILoop.run(..., rounds=6, resume_root=...)`；保留 `run_round()` 兼容旧测试。
- [ ] 默认编辑预算采用 `[3, 3, 2, 2, 1, 1]`，每轮记录预算和实际 edit 数量。
- [ ] 每轮固定记录 champion baseline、candidate diff、diagnosis、provider record、verification、split reports、decision 和 rollback point。
- [ ] 每轮写 `checkpoint.json`；resume 前校验 contract、dataset、evaluator、provider、model 和代码 hash。
- [ ] 已完成轮次不可重评分；只重试明确未完成的 provider/executor 阶段。
- [ ] 将被拒绝候选作为负证据存入 registry，防止相同 patch 无限重复。
- [ ] 记录 token、tool calls、step 数、wall time、磁盘/渲染成本；provider 不支持时写 `unavailable`。
- [ ] 实现一轮与六轮的继承性测试：后续候选必须读取上一轮批准的版本和证据，而不是只读取当前任务反馈。
- [ ] 保持 promotion gate：develop 严格提升、regression 无关键退化、hidden/OOD 不恶化、安全和成本通过。

### G3 验收

- deterministic provider 可完成六轮并可从中断 checkpoint 恢复。
- Codex/Ollama provider 能够在隔离 workspace 生成结构化 candidate 或明确返回 unavailable/timeout。
- 重复候选被拒绝或剪枝；候选不能修改 evaluator、hidden、promotion 或 registry。
- 六轮结果能够证明至少一个版本被持久化并在后续轮次被读取。
- 每轮有完整证据链，且 resume 不改变已完成报告。

---

## 阶段 4：外部数据接入与质量门禁

### 目标

用有官方来源和可核验许可的数据替换正式研究中的项目自生成 fixture；保留 fixture 作为工程回归集。

### 优先级

1. OfficeBench：三类 Office 任务，作为主外部候选。
2. SpreadsheetBench：Excel 子实验和外部验证。
3. Windows Agent Arena 或 OSWorld Office 子集：真实桌面执行扩展，视环境和许可门禁决定。
4. SpreadsheetBench 2：作为后续商业表格扩展，不进入首个主结果，直到许可和运行依赖确认。

### 文件

- 创建：`project_artifacts/phase3_experiments/data/external/README.md`
- 创建：`project_artifacts/phase3_experiments/data/external/source_manifest.json`
- 创建：`project_artifacts/phase3_experiments/scripts/fetch_external_data.py`
- 创建：`project_artifacts/phase3_experiments/scripts/quality_check_external.py`
- 创建：`project_artifacts/phase3_experiments/data/dataset_card.md`
- 创建：`project_artifacts/phase3_experiments/data/data_quality_report.json`
- 修改：`project_artifacts/phase3_experiments/data/README.md`
- 创建：`tests/test_external_dataset.py`

### 实施步骤

- [ ] 为每个数据集记录官方 URL、论文、版本、下载时间、许可证文本、checksum、字段和再分发限制。
- [ ] 许可证未确认时只保存 metadata，不下载任务文件或输入 artifact。
- [ ] 通过官方接口或官方仓库获取 raw 数据；不使用来源不明的二次镜像。
- [ ] 生成 `raw`、`interim`、`processed`、`public`、`protected` 层；hidden/test 不进入 candidate-facing export。
- [ ] 按 template family、来源和近重复内容划分 evolve/develop/regression/hidden/OOD，先分组再切分。
- [ ] 执行格式、缺失、重复、字段、敏感信息、许可证和泄漏检查。
- [ ] 将外部 benchmark 的官方 evaluator 与本项目 evaluator 版本分开记录，不混用分数。

### G4 验收

- 至少一个外部数据集完成来源、许可、checksum 和质量报告。
- 正式候选数据不少于 90 个任务，三类 Office 每类不少于 30 个，或明确记录真实可用数量和原因。
- hidden/OOD 的来源族与 public/evolve 不重叠。
- 数据质量脚本可重复运行，任何 split 漂移都会失败关闭。

---

## 阶段 5：正式 pilot、对照和消融实验

### 目标

先用小规模外部数据验证实验协议、成本和方差，再决定是否投入完整主实验。

### 实验组

| 编号 | 配置 | 目的 |
|---|---|---|
| B0 | 固定 Skill | 无改进基线 |
| B1 | Self-Refine/单任务反馈 | 反思基线 |
| B2 | 候选生成但无独立验证 | 生成器消融 |
| B3 | 候选生成 + verifier | 验证器效果 |
| B4 | 生成 + verifier + frozen evaluator | 评估器独立性效果 |
| B5 | 完整 WorkAgent-RSI | 主方法 |

### 文件

- 创建：`project_artifacts/phase3_experiments/scripts/run_formal.py`
- 创建：`project_artifacts/phase3_experiments/configs/baselines.json`
- 创建：`project_artifacts/phase3_experiments/configs/formal_matrix.json`
- 创建：`project_artifacts/phase3_experiments/reports/pilot_report.md`
- 创建：`tests/test_formal_runner.py`
- 修改：`project_artifacts/phase3_experiments/README.md`

### 设计

- [ ] 主比较预注册为 `B5 vs B1`，辅助比较为 `B5 vs B0/B2/B3/B4`。
- [ ] 先运行 30 个外部 pilot 任务、3 个固定种子；pilot 只用于检验协议、方差和成本，不作为最终主结果。
- [ ] 每次 invocation 固定 executor、model/provider、evaluator、预算和 seed；所有配置写入结果目录。
- [ ] 每个 arm 都运行 develop、regression、hidden、OOD；hidden 只返回聚合指标。
- [ ] 主要指标：task success、artifact correctness、critical regression、hidden/OOD delta、unsafe action rate。
- [ ] 次要指标：结构/视觉质量、轮数、token、tool calls、wall time、cost、每个 validated gain 的成本、跨域 transfer。
- [ ] 不使用人工标注；自动视觉模型不可用时记录 unavailable，并报告覆盖率而不是补分。
- [ ] 预设停止条件：外部数据质量失败、provider 无法稳定运行、成本超过 contract、或 B0/B1 评估不可复现时停止主实验。

### G5 验收

- B0-B5 的命令和配置可复现。
- pilot 结果有成功、失败、unavailable 的完整记录，没有隐去失败运行。
- 统计脚本能生成任务级配对表、均值、置信区间和成本表。
- 只有当评估器可靠性、provider 覆盖率和成本满足 contract 时，才批准阶段 6。

---

## 阶段 6：正式主实验与论文级交付

### 目标

在冻结的外部数据和实验合约上运行主实验、消融、迁移和稳定性分析，输出可复查的论文材料，并推送到 GitHub。

### 文件

- 修改：`project_artifacts/phase3_experiments/scripts/run_formal.py`
- 创建：`project_artifacts/phase3_experiments/scripts/analyze_formal_results.py`
- 创建：`project_artifacts/phase3_experiments/reports/formal_results.md`
- 创建：`project_artifacts/phase3_experiments/reports/statistics.json`
- 创建：`project_artifacts/phase3_experiments/reports/reproducibility.md`
- 创建：`project_artifacts/phase3_experiments/results/` 的索引文件；具体运行仍写入 `project_artifacts/results/experiments/`
- 修改：`README.md`
- 修改：`docs/project_overview_zh.md`
- 修改：`docs/literature_review.md`
- 修改：`Agent.md`
- 创建：`docs/paper/experiment_protocol_zh.md`
- 创建：`docs/paper/tables/` 和 `docs/paper/figures/`

### 实验和统计

- [ ] 正式数据至少三类 Office、每类不少于 30 个任务；正式主结果建议 5 个种子，资源不足时先完成 3 个种子并明确标记。
- [ ] 任务级配对比较，使用 paired bootstrap 95% CI 和 McNemar test；多重比较使用预先声明的校正方法。
- [ ] 报告每个任务的结果分布、split coverage、unavailable 数量和失败原因，不只报告平均分。
- [ ] 分别报告“当前 agent 变强”和“后续候选生成/选择变强”，不把一轮任务反思写成完整 RSI。
- [ ] 报告被拒绝候选、回归、rollback、成本和后续技能复用；不要只保留最佳版本。
- [ ] 生成 CSV、JSON、Markdown 和必要的 XLSX；图表只从 JSON/CSV 自动生成。
- [ ] 生成最终 README、项目介绍、实验协议和限制说明。
- [ ] 运行全量测试、compileall、数据质量、结果 schema、`git diff --check` 和 secret scan。
- [ ] 确认没有 Office/LibreOffice 残留进程，再创建最终 commit、tag 并推送到 GitHub 当前远程分支。

### G6/G7 验收

- 正式实验可以从 Git commit、contract、dataset fingerprint 和命令重现。
- 所有结果有状态和 evidence path；失败或 unavailable 不被隐藏。
- 论文主表、消融表、迁移表和成本表来自自动分析脚本。
- 文档明确区分 pilot、qualification、正式主实验和未执行内容。
- GitHub 分支推送成功，远程 commit 与本地最终 commit 一致。

---

## 失败恢复与回滚协议

- provider 超时：保留 stdout/stderr 和 provider record，标记 `timeout`，不重写已有结果；只在新的 invocation 重试。
- provider 不可用：标记 `unavailable`，不把该运行放入成功率分母以外而隐瞒覆盖率；报告 coverage。
- evaluator hash 变化：旧 contract 不再重评分，创建新实验根目录。
- split 或许可证变化：停止正式实验，保留原始 manifest，重新申请 G4。
- candidate 通过 develop 但破坏 regression/hidden/OOD：拒绝并记录 negative evidence，champion 不变。
- 新版本部署后出现回归：使用 `Store.rollback_to()`，保存回滚证据和前后版本 hash。
- 任意阶段连续三次因同一外部条件无法取得新证据时，标记 blocked 并向用户报告具体阻塞，不伪造完成。

## 统一验证命令

```powershell
py -3.12 -m pytest -q --basetemp="$env:TEMP\\workagent-rsi-tests"
py -3.12 -m compileall -q src tests project_artifacts/phase3_experiments/scripts
py -3.12 project_artifacts/phase3_experiments/data/quality_check.py
py -3.12 project_artifacts/phase3_experiments/scripts/check_office_capabilities.py
git diff --check
```

正式实验命令必须由对应阶段 contract 生成，不允许手工改写已有 invocation 的配置或结果。

## 执行方式

本方案现在只作为待审批计划保存。收到批准后，默认从阶段 0 开始；每个阶段结束会先给出实际证据和 Gate 结论，再等待下一阶段批准。执行时使用 `superpowers:executing-plans`，每个可独立验证的任务单独提交 Git commit。
