# WorkAgent-RSI：评估、验证、动态执行与抗过拟合 Codex 实施计划

> 2026-10-29 用户方向变更：任务合理性、产物完成度、分数和缺陷由 LLM 判断。T10–T17 中将任务编译成代码检查、按固定权重判分和强制规格覆盖率准入的要求已被替代，不再继续补齐 140 条代码验收项。代码保留通用读取、渲染、重算、模型调用、证据和预算管理；两个 loop 继续使用统一的产物评估，外循环按实际任务结果比较 skill。旧章节与记录仅解释历史实现。当前接口和迁移范围见 [LLM 任务评估协议](../../operations/llm-task-review.md)。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 用户将在自己的本地 Codex 中执行；默认串行，不自行启用子代理。

**Goal:** 让系统能可靠识别 Office 任务缺陷、利用证据修复当前任务，并以隔离、可复现、抗过拟合的实验验证跨任务技能改进。

**Architecture:** 保留 Harness/Run/Learn/Check/Store 公共结构，统一 SharedAssessment 的事实快照与评分/问题报告。新增独立需求验收、受限代码执行、任务修复内循环和家族级泛化验证；候选只能修改执行技能，不能修改判题、隐藏资料和晋级规则。

**Tech Stack:** Python 3.11+（本机优先3.12）、Pydantic、pytest、openpyxl、python-docx、python-pptx、可验证的 Docker 隔离执行、按实际能力选择 Excel/LibreOffice 重算与 Office 渲染、显式配置的模型 API/CLI。

**Spec:** 本文第2节为随计划交付的设计约束；T00将其保存为 `docs/superpowers/specs/2026-10-16-evaluation-rsi-hardening-design.md`。本文件建议放入 `docs/superpowers/plans/2026-10-16-evaluation-rsi-hardening.md`。用户当前授权是撰写计划；实际执行由本地 Codex 按用户启动指令进行。

## Global Constraints

- 审查基线：`fisher-yu-like/workagent-rsi`，`main@43f89d54daed37aba9f0e79a7df79b3288b2f993`。若本机不同，先复核差异，不自动reset。
- 全部测试放根目录 `tests/`；新代码证据放 `project_artifacts/results/hardening-v2/<task-id>/<attempt-id>/`；attempt目录创建后不覆盖。
- 默认串行，进度账本只允许一个 task 为 in_progress；不删除用户改动、失败运行或旧报告。
- 未实际运行的测试/模型/Office/渲染/人工审阅一律标记 not_run、blocked、incomplete 或 unavailable，禁止fake。
- 禁止使用Ollama开展本轮真实实验；保留旧Ollama历史记录和明确的测试替身，不默认删除兼容实现。
- 正式执行技能只允许修改 `WorkAgentSkill.instructions`；不得修改 evaluator/verifier、保护集、权限、安全策略、原始输入与晋级规则。更新评估基础设施属于本计划工程实施，必须新版本/新身份，候选优化期间冻结。
- 必须拒绝题目专属答案、按task_id分支、固定输入范围和固定文案；允许通用API知识、动态算法及用户明确指定的文档模板。
- 模型生成代码不得在宿主无限制执行；隔离后端不可用不降级。候选、执行、评估侧数据和权限分开。
- 未完成的质量检查不以0或推测补齐；已确认执行失败可记任务不成功，但无产物的视觉/语义质量仍为null。
- 付费/真实调用默认关闭；用户给出可执行预算并启用之前只运行单元、stub与dry-run。不得读取/打印/写入真实密钥；endpoint不得带凭据。
- 不默认推送、开PR、合并或部署。完成本地验证后按阶段提交；需要外部发布由用户另行授权。
- 工程资格、真实模型闭环、研究收益和外部benchmark资格分级；任何一级不能替代下一级的证据。

## Review Focus

1. 说明文字很完整但constraints缺失：不能只验可读性后声称任务满分；T10/T17测试。
2. 文件看起来有目标文字但错位、越界或被遮挡：需要位置与可见性证据；T12/T15测试。
3. 代码失败没有产物与API环境失败：归因、成功率与质量分母必须不同；T20测试。
4. 输入变体、源文件编辑及任务ID改名：输出应遵循当前输入与授权变更；T14/T23/T24测试。
5. 缓存、重试、模型切换和跨历史结果汇总：不重复计数、不伪装独立复评、不混合声明；T09/T16/T29/T30测试。

---

## 1. 使用方式和证据边界

这是一份待执行计划，不是已完成报告。所有命令后的PASS均表示期望验收结果，不能复制成实际结果。计划中列出的新增文件/类型是拟实现接口，不代表当前仓库已有。

### 1.1 审查时实际观察

| 项目 | 观察 | 解读边界 |
|---|---|---|
| 全量测试，Linux原样 | 145 passed / 7 failed / 1 skipped | 5个失败受Windows `py -3.12`启动器影响 |
| 临时兼容启动器后 | 150 passed / 2 failed / 1 skipped | 仍有旧Word fixture/晋级测试问题；未改业务代码 |
| evaluator/verifier相关选定测试 | 63 passed | 证明已编码场景通过，不能证明现实缺陷检出率 |
| 代码静态检查 | compileall及diff检查通过 | 不代表真实模型或Office资格 |
| 合成反例 | 空白Excel、错段落、PPT画布外文字、包含式覆盖获得100分且零issue | 前两类与规格/作用域有关，后两类涉及可见性覆盖；不是所有任务都已声明这些要求 |
| 等价公式 | `=B2+B3` 与预期 `=SUM(B2:B3)` 被判不同 | 精确公式任务可合理拒绝；允许等价解任务需要结果/变体验证 |
| API候选 | 请求不含当前champion技能内容 | 已以请求捕获复现 |
| 执行隔离 | 临时父目录文件和虚假环境变量可被run_python读取 | 未读取真实凭据或真实保护数据 |
| 汇总 | pilot=0与formal=1输出mean=0.5，claims_allowed=true | 以临时summary复现，无正式结果被本轮修改 |
| 最新真实外循环报告 | 2026-10-15，四split各1题，全满分，候选拒绝 | Git内仅见报告；原始记录未齐备，不能独立复核全部真实运行 |

### 1.2 在本地先做什么

1. 将本计划保存进仓库建议路径，执行T00确认本地现状。
2. 默认使用 `.venv` 的Python，命令显式指向解释器；不要依赖全局 `python` 或Windows launcher。
3. 修复阶段只运行拥有者任务的相关测试；T01红灯反例在所属任务修复前保留。最终T34必须全量跑完，不能用选择性测试宣布全绿。
4. 一个task完成后审阅diff、记录证据，再开始下一个；不需要每个小task找用户确认。

Windows PowerShell约定（仓库根目录）：

```powershell
# 创建环境是本地实施动作；先确认已有环境，存在则复用，不覆盖。
py -3.12 -m venv .venv
$TaskPython = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $TaskPython -m pip install -e ".[test]"
& $TaskPython -m pytest -q
```

Linux/macOS约定：

```bash
python3.12 -m venv .venv
TASK_PYTHON="$PWD/.venv/bin/python"
"$TASK_PYTHON" -m pip install -e '.[test]'
"$TASK_PYTHON" -m pytest -q
```

若依赖安装受限，记录实际错误；不猜测测试结果。API/Office能力不在pip安装完成后自动视为可用。

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

## 3. 任务地图与阶段门禁

| 阶段 | Tasks | 门禁 |
|---|---|---|
| A 基线与契约 | T00–T03 | G0：基线可复查、状态/证据接口固定 |
| B 执行边界/候选/统计 | T04–T09 | G1：真实隔离探针通过，候选和统计反例转绿 |
| C evaluator完整性 | T10–T17 | G2：需求/位置/公式/保持/视觉范围明确，公共入口一致 |
| D verifier及任务修复 | T18–T22 | G3：诊断有证据、内循环可复查、预算和保护权限有效 |
| E 动态执行与模板清理 | T23–T24 | G4：正式路径无已知题目答案，输入变体行为通过 |
| F 校准与数据隔离 | T25–T28 | G5：独立缺陷校准通过；人类/真实judge资格单列 |
| G 统计RSI与真实资格 | T29–T31 | G6：真实provider/修复/外循环证据完整，结论不超范围 |
| H 收益/外部/交接 | T32–T35 | G7：对照、公平预算、封存测试和发布等级有真实证据 |

默认按编号顺序执行；依赖满足时可先完成独立离线task，不自动启动并行代理。G1真实隔离未通过不得执行生成代码的真实资格；G5人类标签未完可以完成结构工程资格，不能宣称完整质量或研究资格。

### 每个task的统一操作顺序

1. 读Files和Interfaces，确认依赖已完成；保存task起始commit和输入身份。
2. 先写下面列明的独立失败测试并运行红灯，记录具体失败；已有反例直接复用。
3. 按步骤实现最小变更，不顺手改其他评分/数据/提示词。
4. 跑task指定测试，检查diff和真实输出，记录退出码及尚未覆盖范围。
5. 本地提交本task或清晰阶段边界，记录commit；有意保留的未来task红灯不隐藏。不得 `git add .`误提交凭据/大产物。

下面的断言代码是测试行为契约，用例名与fixtures由实现者写成实际pytest；它们不是现有可运行测试文件。新增接口未实现时红灯是预期；实现后所属task测试必须真绿。所有验收命令使用 `$TaskPython`（PowerShell）或 `$TASK_PYTHON`（Bash）。

## 4. 逐个小task

### T00：冻结本机基线与审查差异

**阶段/依赖：** A；无。

**Files：** 修改：`project_artifacts/execution_plan.md`、`project_artifacts/execution_log.md`；新增：`docs/superpowers/specs/2026-10-16-evaluation-rsi-hardening-design.md`；新增：`tests/test_environment_manifest.py`；新增：`src/workagent_rsi/environment_manifest.py`。

**Interfaces：** `capture_environment(repo: Path, output: Path) -> dict`：输出提交、dirty 文件路径、解释器、依赖版本、CLI/API 协议能力与 Office/渲染能力；不输出环境变量值、密钥和用户配置内容。

- [ ] **1. 补失败测试。** 在 `tests/test_environment_manifest.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert manifest["git_commit"]
assert manifest["python_version"] >= "3.11"
assert "api_key_value" not in manifest
assert original_dirty_files_unchanged is True
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 确认实际仓库根目录与当前提交，读取 AGENTS.md（如有）、Agent.md、README 和本计划。记录是否与 43f89d5 一致；不同则先读差异并把已失效发现标记为需复核，禁止强制回退。把本计划第 2 节复制为设计文档并记录来源。原工作区存在用户改动时，保留原地改动，使用独立 worktree/分支开展实现。环境检查只探测能力，不启动付费请求。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_environment_manifest.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_environment_manifest.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 本机原始全量测试退出码及失败清单已保存；缺失 Windows 启动器和真正逻辑失败分开记录。设计和进度文档已落盘，明确当前只执行 T00，不启动真实实验。

**证据：** `T00/<attempt-id>/` 下保存 baseline/environment.json、baseline/test-baseline.txt、baseline/git-status.txt、baseline/assessment-boundary.md；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无法识别用户工作区或有冲突需用户决定时停止涉及该工作区的修改；独立只读审查可继续。

---

### T01：把审查反例变为独立回归证据

**阶段/依赖：** A；T00。

**Files：** 新增：`tests/test_review_regressions.py`、`tests/test_candidate_boundary_regressions.py`；新增：`tests/fixtures/review_cases/manifest.json`；测试内生成临时 Office 文件。

**Interfaces：** `review_case_id` 采用 R01–R12；fixture 标签明确来自任务约束/独立计算/可验证几何，不使用被测评分器作为真值。修复前保留当前失败输出；失败用例不删除、不永久 xfail。

- [ ] **1. 补失败测试。** 在 `tests/test_review_regressions.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert task_score_is_not_full_for_blank_analysis
assert wrong_location_is_not_pass
assert off_slide_text_is_not_visual_pass
assert raw_over_budget_patch_is_rejected_whole
assert mixed_cohorts_cannot_authorize_formal_claim
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 逐个复现：空白文件获得任务满分；位置约束被全局搜索绕过；PPT 画布外文字；包含式遮挡；合法等价公式；独立 CandidateVerifier 接受未知字段；API 候选缺少 champion；超预算 patch 被截断；pilot/formal 混合；最终评分失败不触发修复；代码执行错误不进入反馈；父目录/虚假环境变量可被生成脚本读取。只操作自建临时文件，不读取真实隐藏集或真实凭据。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_review_regressions.py tests/test_candidate_boundary_regressions.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_review_regressions.py tests/test_candidate_boundary_regressions.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 每个反例都有 case_id、最小输入、期望、当前观察和负责修复任务；预期红灯是基线证据，不伪称已修复。等价公式案例的自然语言明确允许任意等价求和表达式；精确公式要求另建应拒绝对照。

**证据：** `T01/<attempt-id>/` 下保存 review-regressions/red-baseline.json、red-pytest.txt、case-owner-map.json；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T02：解释器可移植性与两个旧失败用例修正

**阶段/依赖：** A；T00、T01。

**Files：** 修改：`src/workagent_rsi/verifier.py`、`tests/test_frozen_evaluator.py`、`tests/test_rsi_loop.py`、`tests/test_multiround_rsi.py`、`tests/test_simple_harness.py`、`tests/test_verifier.py`。

**Interfaces：** 默认编译/pytest 子进程使用 `sys.executable`；保留 runner 注入。检查命令身份要记录真实 executable，不将 Linux 伪装成 Windows。

- [ ] **1. 补失败测试。** 在 `tests/test_verifier.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert command[0] == sys.executable
assert wrong_baseline_has_actual_missing_requirement
assert fixed_candidate_repairs_that_requirement
assert rollback_restores_previous_hash
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 先测试无 py 启动器仍可验证。修正 Word fixture：任务说明不得被直接复制成含答案的标题，使 baseline 错误确实出现在成品；独立确认目标字串的预期位置。重新核对旧闭环晋级场景，保证 baseline 真失败、候选真修复且 rollback 有效。禁止改阈值或改断言来掩盖正确 baseline 无提升。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_verifier.py tests/test_frozen_evaluator.py tests/test_rsi_loop.py tests/test_multiround_rsi.py tests/test_simple_harness.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_verifier.py tests/test_frozen_evaluator.py tests/test_rsi_loop.py tests/test_multiround_rsi.py tests/test_simple_harness.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 两项已知逻辑失败的原因各有记录；相关测试在原生本机解释器通过。T01 中尚未修复反例继续单列为 expected-open，不把全量套件描述为全绿。

**证据：** `T02/<attempt-id>/` 下保存 portability/focused-tests.txt、legacy-fixture-explanation.md；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T03：运行证据、状态和协议能力契约

**阶段/依赖：** A；T02。

**Files：** 新增：`src/workagent_rsi/run_contracts.py`、`src/workagent_rsi/evidence_bundle.py`；修改：`src/workagent_rsi/contracts.py`、`src/workagent_rsi/costs.py`；新增：`tests/test_run_contracts.py`、`tests/test_evidence_bundle.py`。

**Interfaces：** 新增 `ExecutionOutcome(status, failure_origin, artifact_refs, trace_refs, usage)`、`AssessmentOutcome(status, score, coverage, report_refs)`；`FailureOrigin` 固定为 environment/agent_execution/artifact_defect/assessment_gap/spec_gap。`write_evidence_bundle(root: Path, record: dict) -> Path` 返回可移植 manifest 路径。

- [ ] **1. 补失败测试。** 在 `tests/test_run_contracts.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert absent_usage["tokens"] is None
assert execution_failure.origin == "agent_execution"
assert transport_timeout.origin == "environment"
assert moved_bundle_is_resolvable_without_windows_absolute_paths
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 保留旧返回字段适配层。以相对路径记录 bundle 内文件、SHA-256、模型配置、代码/输入/技能/规格身份、时间与状态。区分 chat/completions、responses、图像输入与 structured-output 能力；执行器协议可用不得自动推断 judge 协议可用。未知成本为 null + unavailable；零必须有实际观测。record 内不保存 Authorization。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_run_contracts.py tests/test_evidence_bundle.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_run_contracts.py tests/test_evidence_bundle.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 所有后续模块可使用同一失败分类和证据引用；旧结果仍可读，历史文件不覆盖。能力探测使用 stub；真实探测由 T31 控制。

**证据：** `T03/<attempt-id>/` 下保存 contracts/schema-v2.json、bundle-example/manifest.json、compatibility-tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T04：建立真正受限的生成代码执行后端

**阶段/依赖：** B；T03。

**Files：** 新增：`src/workagent_rsi/execution_sandbox.py`、`deploy/agent-runtime/Dockerfile`、`deploy/agent-runtime/requirements.lock`；修改：`src/workagent_rsi/workagent_provider.py`；新增：`tests/test_execution_sandbox.py`。

**Interfaces：** `SandboxPolicy` 定义网络、挂载、资源、身份与镜像 digest；`SandboxExecutor.probe() -> dict`；`SandboxExecutor.run(script: Path, workspace: Path, timeout_seconds: int) -> ExecutionOutcome`。API/Ollama 的 run_python 必须经过此接口。Codex CLI 自带 sandbox 路径单独记录能力，不替代该后端的验收。

- [ ] **1. 补失败测试。** 在 `tests/test_execution_sandbox.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert parent_sentinel_read_is_denied
assert dummy_host_secret_is_absent
assert network_probe_is_denied
assert source_input_hash_is_unchanged
assert timed_out_container_and_descendants_are_gone
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 默认实现一次性 Docker 容器：--network=none、--read-only、--cap-drop=ALL、no-new-privileges、非 root UID/GID、pids<=128、memory<=2GiB、cpus<=2；可写临时目录使用 tmpfs；仅任务最小输入和脚本只读挂载，outputs/ 与 scratch/ 单独可写。禁止宿主仓库、隐藏数据、Docker socket、HOME、用户配置和密钥挂载。宿主进行模型 HTTP 请求；容器仅收到净化后白名单环境变量。运行镜像预装锁定依赖并记录 digest，运行中不联网安装。超时删除本次容器并确认子进程消失。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_execution_sandbox.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_execution_sandbox.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 单元测试检查实际容器参数；真实隔离探针在用户本机运行并留证。后端不可用时返回 environment/unavailable，禁止退回宿主 subprocess 执行模型脚本。Docker 测试可以显式 skip，但 G1 隔离验收不得因此通过。

**证据：** `T04/<attempt-id>/` 下保存 sandbox/probe.json、policy.json、image-digest.txt、boundary-tests.json、timeout-cleanup.json；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 本机没有 Docker/合适隔离能力、需要安装或系统设置时请求用户处理；可继续不依赖真实执行的任务。

---

### T05：保护评估侧资料及 Office 渲染边界

**阶段/依赖：** B；T04。

**Files：** 修改：`src/workagent_rsi/workagent_office.py`、`src/workagent_rsi/candidate_workspace.py`、`src/workagent_rsi/artifact_renderer.py`、`src/workagent_rsi/artifact_com.py`；新增：`tests/test_evaluation_isolation.py`。

**Interfaces：** `prepare_execution_view(task, input_base: Path, destination: Path) -> dict` 只导出任务允许输入；`RenderPolicy` 固定只读副本、宏禁用、外部更新禁用、进程所有权。渲染器接口保持 `render(path, domain, artifact_sha256) -> RenderResult`。

- [ ] **1. 补失败测试。** 在 `tests/test_evaluation_isolation.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert hidden_files_not_mounted
assert source_symlink_is_rejected
assert unrelated_office_process_survives
assert input_artifact_hash_before == input_artifact_hash_after
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 候选和生成代码运行视图不包含任何历史/隐藏评分资料。补齐导出源符号链接检查，必须在 resolve 之前逐段 lstat。渲染与重算仅处理校验过的副本，禁宏/禁外链更新，在隔离 Office worker/专用账户或受控环境内进行。禁止“杀掉启动后出现的所有 Office 进程”，仅清理本次调用创建的进程/应用实例。记录 Office、Poppler、字体/系统环境指纹；不能隔离的能力保持缺口。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_evaluation_isolation.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_evaluation_isolation.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 路径检查、OS 隔离、评估侧数据隔离均有独立证据。COM 仅“重开成功”不得描述为公式重算或视觉验证通过。

**证据：** `T05/<attempt-id>/` 下保存 sandbox/evaluation-boundary.json、office-worker-policy.json、process-cleanup-tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 配置专用 Office worker/账户需要用户参与；不得擅自终止用户 Office 或修改全局安全设置。

---

### T06：候选生成输入包含 champion 与受控历史

**阶段/依赖：** B；T03。

**Files：** 修改：`src/workagent_rsi/candidate_provider.py`、`src/workagent_rsi/rsi_loop.py`、`src/workagent_rsi/rsi_feedback.py`；新增：`tests/test_candidate_context.py`。

**Interfaces：** 新增 `CandidateContext(parent_version, champion_package, champion_hash, develop_feedback, public_lessons, edit_budget)`；API 与 CLI provider 共用 `build_candidate_context(...) -> CandidateContext`；`generate_with_context(context, workspace, record_root)` 为新接口，旧 generate_with_feedback 保留适配。

- [ ] **1. 补失败测试。** 在 `tests/test_candidate_context.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert champion_sentinel in captured_request
assert captured_context.champion_hash == registered_hash
assert hidden_sentinel not in serialized_context
assert previous_public_lesson_is_present
assert over_budget_context_is_explicit
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 从实际导出的 skill.json 读取当前技能，核对 registry/package hash 后纳入请求。保留可见 develop 的事实、最小轨迹摘要和任务需求引用；不发送 regression/hidden/OOD 内容、路径或任务级结论。public_lessons 必须有 develop 来源和抽象内容，不将 hidden 拒绝原因转换成提示。长度超预算必须显式失败或按固定可记录策略压缩，保留 champion 关键规则；禁止静默截断。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_candidate_context.py tests/test_candidate_provider.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_candidate_context.py tests/test_candidate_provider.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 第二轮请求实际包含上一轮 champion，而非仅父版本字符串；API/CLI 上下文策略一致；保存脱敏 request 和 context hash。

**证据：** `T06/<attempt-id>/` 下保存 candidate-context/request-redacted.json、context.json、visibility-tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T07：完整校验候选原始响应与确定性归一化

**阶段/依赖：** B；T06。

**Files：** 修改：`src/workagent_rsi/candidate_provider.py`、`src/workagent_rsi/rsi_contracts.py`；新增：`tests/test_candidate_normalization.py`。

**Interfaces：** `normalize_candidate(raw: dict, context: CandidateContext) -> CandidatePatch`；另输出 `normalization_record`，记录原始字段到标准字段映射。模型身份以实际 provider record 为权威，响应自报仅作原始数据。

- [ ] **1. 补失败测试。** 在 `tests/test_candidate_normalization.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert two_edits_with_budget_one_is_rejected
assert forbidden_second_edit_is_not_hidden
assert normalized_instruction == raw_instruction
assert provider_record_identity_is_authoritative
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 先检查完整 edits 列表，再执行格式转换；删除 [:edit_budget] 静默截断。只支持已登记 envelope 版本，禁止补造原因、诊断引用或“实际模型”。缺字段可用确定性上下文元数据补充但必须记录 provenance；模型未提供的假设保持缺失/拒绝，不能伪造模型推理。任何超预算/禁止目标/重复互相覆盖字段整体拒绝。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_candidate_normalization.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_candidate_normalization.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 合法格式变体仍可解析；原始内容和转换记录可复查；不再出现删除违规项后接受剩余项的行为。

**证据：** `T07/<attempt-id>/` 下保存 candidate-normalization/valid-and-invalid-cases.json、tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T08：CandidateVerifier 独立完成技能验证

**阶段/依赖：** B；T02、T07。

**Files：** 修改：`src/workagent_rsi/verifier.py`、`src/workagent_rsi/leakage.py`、`src/workagent_rsi/rsi_loop.py`；新增：`tests/test_candidate_skill_validation.py`。

**Interfaces：** `verify(candidate, workspace, policy, *, skill_model, parent_package, parent_version, edit_budget, behavior_probe=None) -> VerificationReport`；VerificationReport 增加 schema/safety/behavior 各自状态，保留兼容 passed。

- [ ] **1. 补失败测试。** 在 `tests/test_candidate_skill_validation.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert standalone_verifier_rejects_unknown_field
assert wrong_parent_is_rejected
assert int_instructions_is_rejected
assert compile_not_applicable_is_not_behavior_pass
assert protected_behavior_regression_blocks_candidate
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 集中原先外循环中的 allowlisted field、父版本、预算、严格类型验证。先对完整 patch 检查，再在内存中应用至 parent_package 并验证模型；仅 instructions 可改，version 由 registry 管理。JSON/纯提示词明确记录 compile=not_applicable，不能靠编译空目录宣称技能验证有效。行为探针使用独立固定任务并在 T04 隔离环境运行；候选自带测试仅作补充。检查未知字段、错误类型、弱化必保留规则和 task_id 分支。关键词检测仅是辅助，不能替代隔离/行为验证。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_candidate_skill_validation.py tests/test_verifier.py tests/test_rsi_artifact_feedback.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_candidate_skill_validation.py tests/test_verifier.py tests/test_rsi_artifact_feedback.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 独立调用与 RSI 调用结果一致；验证失败不更新 champion；无真实行为探针时保持 behavior=not_run，不声称已验证质量。

**证据：** `T08/<attempt-id>/` 下保存 candidate-verifier/report-examples.json、focused-tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T09：按可比实验分组并修复正式声明门禁

**阶段/依赖：** B；T03。

**Files：** 修改：`project_artifacts/phase3_experiments/scripts/analyze_formal.py`；新增：`src/workagent_rsi/result_cohorts.py`、`tests/test_result_cohorts.py`。

**Interfaces：** `CohortKey(mode, dataset_hash, split_hashes_hash, evaluator_hash, acceptance_hashes_hash, model_config_hash, experiment_arm, budget_policy_hash)`；`analyze_cohorts(root: Path) -> dict` 输出分组报告和排除原因。

- [ ] **1. 补失败测试。** 在 `tests/test_result_cohorts.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert mixed_pilot_formal_global_mean_is_absent
assert pilot_zero_and_formal_one_remain_separate
assert unknown_identity_claims_allowed is False
assert duplicate_run_does_not_inflate_sample_count
assert nan_metric_is_rejected
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 禁止按同名指标跨 pilot/formal、不同数据/模型/评估器/预算/实验组直接平均。run_id+attempt_id 去重，明确重试选择规则；不把成功重试与失败原运行重复计算。只有来源可验、配置可比、任务覆盖完整且经入场门禁的 formal cohort 才允许声明；身份缺失/非有限数值/重复证据不进入数字聚合。旧版本统一评估时创建新的 reference_eval_run，保留原始历史，逐任务配对比较。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_result_cohorts.py tests/test_formal_runner.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_result_cohorts.py tests/test_formal_runner.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** T01 混合反例转绿；每个数字能追溯分母和 cohort；不以一个合法 formal summary 授权整个目录的混合结果。

**证据：** `T09/<attempt-id>/` 下保存 analysis/cohort-report.json、excluded-records.json、paired-reference-example.json；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T10：建立需求清单及验收规格入场检查

**阶段/依赖：** C；T01、T03。

**Files：** 新增：`src/workagent_rsi/requirement_coverage.py`；修改：`src/workagent_rsi/assessment_contracts.py`、`src/workagent_rsi/artifact_assessment.py`；新增：`tests/test_requirement_coverage.py`。

**Interfaces：** `TaskRequirement(requirement_id, source_quote, source_ref, obligation, validation_method, check_ids)`；`RequirementInventory(task_id, requirements, reviewed, provenance)`；`validate_spec_coverage(task, inventory, spec, *, evaluation_profile) -> SpecAdmissionReport`。profile 固定为 structural_only/task_acceptance/research。

- [ ] **1. 补失败测试。** 在 `tests/test_requirement_coverage.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert blank_file_for_analysis_task.status == "SPEC_INCOMPLETE"
assert structural_only_result.task_score is None
assert all_mandatory_requirements_have_check_ids
assert generated_inventory_without_review_cannot_admit_research
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 从任务和授权输入建立独立需求清单，用户意图必须可追溯到原文。模型可辅助提取，但清单需 reviewed 或来自已审基准，不能把模型自报“完整”当证据。每项要求绑定确定性/语义/视觉/人工验收或明确未覆盖；未覆盖的强制要求在 task_acceptance/research 中返回 SPEC_INCOMPLETE。没有任务要求的 structural_only 可只验可读性，但不得显示任务总分/成功。兼容旧 spec 时标注 legacy_unreviewed，不自动视为需求完整。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_requirement_coverage.py tests/test_review_regressions.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_requirement_coverage.py tests/test_review_regressions.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 报告分别呈现需求覆盖和检查完成率；不再把 file.readable 满分当完整任务满分。正式 spec 在候选产物出现前冻结。

**证据：** `T10/<attempt-id>/` 下保存 specs/requirement-inventory.json、spec-admission.json、coverage-tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 真实任务存在无法从原文确定的强制要求时请求用户澄清；不自行增加主观业务要求。

---

### T11：检查注册表、类型及适用范围预检

**阶段/依赖：** C；T10。

**Files：** 新增：`src/workagent_rsi/check_registry.py`；修改：`src/workagent_rsi/assessment_contracts.py`、`src/workagent_rsi/artifact_assessment.py`；新增：`tests/test_check_registry.py`。

**Interfaces：** `CheckDefinition(name, domains, required_location_fields, expected_schema, capabilities)`；`validate_acceptance_spec(spec, capabilities) -> SpecAdmissionReport`；注册名统一在 check_registry。

- [ ] **1. 补失败测试。** 在 `tests/test_check_registry.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert excel_cell_without_sheet_is_spec_gap
assert unknown_check_is_rejected_before_execution
assert missing_renderer_is_capability_gap
assert unsupported_legacy_constraint_is_visible
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 执行前检测未知 check、缺 slide/cell、无效范围、空 expected 集合、check 与文件域不匹配、无效权重和关键项。未知检查记为 spec_gap；实际能力缺失记 assessment_gap；不能都归咎成品。约束适配器显式记录每个 legacy key 的转换或未支持原因。保持 partial/unknown/null 与总分逻辑，不允许因解析失败而删掉要求。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_check_registry.py tests/test_artifact_assessment_contracts.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_check_registry.py tests/test_artifact_assessment_contracts.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 预检能解释“规格错误”和“环境缺失”的区别；支持清单与文档自动从 registry 生成，避免漂移。

**证据：** `T11/<attempt-id>/` 下保存 specs/check-registry.json、legacy-adapter-coverage.json、preflight-cases.json；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T12：修复位置检查与内容查找的作用域

**阶段/依赖：** C；T11。

**Files：** 修改：`src/workagent_rsi/artifact_assessment.py`；新增：`src/workagent_rsi/artifact_locations.py`、`tests/test_scoped_content_checks.py`。

**Interfaces：** `resolve_text_scope(obj, location: Location, options: dict) -> list[dict]`；`text.contains` 指定位置时只在该 scope 搜索；未指定位置保留全文模式；定位失败返回 FAIL，配置不合法返回 spec_gap。

- [ ] **1. 补失败测试。** 在 `tests/test_scoped_content_checks.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert phrase_only_in_paragraph_two_fails_paragraph_one_check
assert phrase_on_slide_two_fails_slide_one_check
assert duplicate_heading_location_is_ambiguous
assert localized_heading_style_is_recognized
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 覆盖 Word 段落/标题节/表格单元格，PPT 指定 slide/object/group/table，以及 Excel sheet/cell/range。保留要求位置 requested_location 与实际证据 observed_location 两个字段，不可用实际找到的位置覆盖用户要求。标题使用稳定 style_id/outline 识别并兼容显示语言，不仅依赖英文 Heading 前缀。显式处理重复标题和越界索引，不任取第一个。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_scoped_content_checks.py tests/test_artifact_assessment_documents.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_scoped_content_checks.py tests/test_artifact_assessment_documents.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 错位反例转绿；允许全文查找的旧任务保持兼容，明确位置的任务不可被其他位置文字满足。

**证据：** `T12/<attempt-id>/` 下保存 assessment/scoped-location-cases.json、focused-tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T13：Excel 公式语义与真正重算

**阶段/依赖：** C；T05、T11。

**Files：** 新增：`src/workagent_rsi/spreadsheet_recalc.py`、`src/workagent_rsi/formula_checks.py`；修改：`src/workagent_rsi/artifact_assessment.py`、`src/workagent_rsi/sales_assessment.py`；新增：`tests/test_formula_semantics.py`。

**Interfaces：** `RecalculationEngine.recalculate(source: Path, output: Path) -> RecalcResult`；支持 Excel worker 或 LibreOffice；`formula_exact`、`formula_present`、`recalculated_value` 分开注册。独立期望值来自任务输入 oracle，不读取输出作为真值。

- [ ] **1. 补失败测试。** 在 `tests/test_formula_semantics.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert equivalent_sum_passes_when_semantics_allow
assert exact_formula_requirement_rejects_other_expression
assert hardcoded_twenty_five_fails_changed_input
assert stale_cache_is_not_recalculation_evidence
assert original_sha256_unchanged
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 在副本重算，保存引擎版本、日志和新文件哈希，禁止修改原始提交。精确公式要求仍精确检查；允许等价表达式的任务按重算结果和输入变体测试，不以简单字符串归一化宣称一般公式等价。区分公式文本、旧缓存和本次重算值；外部链接/动态数据源不可用时保留 gap。变体包含末行新增、负值、空值、零和顺序变化，适用性由任务决定。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_formula_semantics.py tests/test_artifact_assessment_excel.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_formula_semantics.py tests/test_artifact_assessment_excel.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 真实引擎探针通过后才声明重算能力；缺引擎时单元测试可通过，重算资格保持 blocked。

**证据：** `T13/<attempt-id>/` 下保存 recalc/engine-probe.json、formula-variants.json、recalc-report.json；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 需要安装 Office/LibreOffice 或隔离 worker 时找用户；不伪造 cached value。

---

### T14：编辑任务的授权修改与源内容保持

**阶段/依赖：** C；T11、T12。

**Files：** 新增：`src/workagent_rsi/preservation_checks.py`；修改：`src/workagent_rsi/assessment_contracts.py`、`src/workagent_rsi/artifact_assessment.py`；新增：`tests/test_edit_preservation.py`。

**Interfaces：** `PreservationSpec(source_hash, allowed_changes, preserved_regions, normalization_policy)`；`compare_preservation(source, output, spec) -> list[CheckRecord]`；对象使用可复核的结构标识，不依赖文件二进制完全一致。

- [ ] **1. 补失败测试。** 在 `tests/test_edit_preservation.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert changed_unrelated_cell_is_defect
assert dropped_source_paragraph_is_defect
assert requested_added_slide_is_allowed
assert metadata_only_change_is_not_business_defect
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** Excel 检查未授权单元格/公式/工作表；Word 检查需保留的段落、表格和标题层级；PPT 检查未授权 slide/object 与页数。允许任务明确要求新增页/表/段落，禁止固定“edit 永不新增”。时间戳、关系 ID 等无意义序列化变化按冻结 normalization 忽略，不能忽略业务文本/数值改变。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_edit_preservation.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_edit_preservation.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 重建文件丢失源内容会被检出；正确编辑不会因 ZIP/OOXML 序列化差异被误拒。

**证据：** `T14/<attempt-id>/` 下保存 preservation/source-output-diff.json、normalization-policy.json、tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T15：PPT 几何风险与视觉证据分工

**阶段/依赖：** C；T05、T11。

**Files：** 修改：`src/workagent_rsi/artifact_assessment.py`、`src/workagent_rsi/judgement_provider.py`、`src/workagent_rsi/artifact_renderer.py`；新增：`tests/test_visibility_checks.py`。

**Interfaces：** 新增 `VisibilityFinding(object_id, kind, evidence, certainty)`；几何 check 保留 bounds/overlap，但包含关系不直接证明可见性。`VisualCoverageLedger` 记录要求页、已渲染页和已检查页。

- [ ] **1. 补失败测试。** 在 `tests/test_visibility_checks.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert off_canvas_required_content_is_not_accepted
assert opaque_containment_is_not_automatic_pass
assert legal_background_is_not_automatic_failure
assert unchecked_required_page_blocks_visual_completion
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 确定越界可按位置规则失败；包含、z-order、实心覆盖、旋转、透明度等作为风险，无法确定时 NEEDS_REVIEW 并请求真实渲染。背景与装饰不能一概视为遮挡。添加画布外文本、白底白字、后置实心覆盖和合法背景正例；图像-only 内容不能仅凭文本缺失判错。长页文档按预定批次覆盖全部必需页，禁止超过8张时直接省略后续页。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_visibility_checks.py tests/test_visual_assessment.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_visibility_checks.py tests/test_visual_assessment.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 本轮两个 PPT 漏判不再获无条件满分；有实际渲染和标注才能声称视觉正确，stub 仅验证管线。

**证据：** `T15/<attempt-id>/` 下保存 visual/coverage-ledger.json、geometry-findings.json、real-render-manifest.json；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 本机无渲染/图像 judge 能力时明确 blocked；不得用生成截图或几何推测替代真实页面。

---

### T16：语义/视觉 judge 校准与长文件证据管理

**阶段/依赖：** C；T03、T12、T15。

**Files：** 修改：`src/workagent_rsi/semantic_assessment.py`、`src/workagent_rsi/model_judgement.py`、`src/workagent_rsi/judgement_provider.py`；新增：`src/workagent_rsi/evidence_partition.py`、`tests/test_judge_evidence_scope.py`。

**Interfaces：** `partition_evidence(items, requirement, budget) -> EvidencePartition`；分片记录包含 coverage ledger 和未覆盖原因；`JudgeResult` 保留逐次 decision、引用、分数和分歧，不把自报 confidence 直接当正确概率。

- [ ] **1. 补失败测试。** 在 `tests/test_judge_evidence_scope.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert quoted_text_does_not_alone_prove_source_accuracy
assert all_required_partitions_have_results
assert cached_decision_independent_calls == 0
assert artifact_instruction_cannot_override_rubric
assert missing_source_returns_needs_review
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 需求要求核对来源时，显式提供授权来源事实及哈希，只给输出正文不能证明事实正确。实现局部要求分片和跨片一致性检查；页眉/页脚/备注/图片文字仅在明确支持的通道检查，缺失内容不误判“不存在”。同一缓存不能算独立复评；独立复评禁用 judge 缓存或使用独立调用标识，文本提取/渲染缓存可复用。注入文字作为数据处理，加入指令注入反例。judge API /responses 能力需独立探测。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_judge_evidence_scope.py tests/test_model_judgement.py tests/test_visual_assessment.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_judge_evidence_scope.py tests/test_model_judgement.py tests/test_visual_assessment.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 保存完整分片覆盖、模型身份、实际调用次数、分歧与来源；真实判断准确率留给 T28 校准，不能由 schema 测试推导。

**证据：** `T16/<attempt-id>/` 下保存 judges/capability-matrix.json、evidence-partitions.json、independent-review-tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T17：评分范围、关键失败与统一公开入口

**阶段/依赖：** C；T10–T16。

**Files：** 修改：`src/workagent_rsi/artifact_evaluator.py`、`src/workagent_rsi/harness_artifact_evaluator.py`、`src/workagent_rsi/check.py`、`src/workagent_rsi/evaluator.py`；新增：`tests/test_assessment_entrypoint_parity.py`。

**Interfaces：** `AssessmentOutcome` 分别公开 task_acceptance、quality_score、spec_admission、task_requirement_coverage、check_completion；`Check.evaluate(..., assessment_profile=...)` 与 Harness 默认复用同一已版本化链路。旧 evaluator 仅显式 legacy 模式可用。

- [ ] **1. 补失败测试。** 在 `tests/test_assessment_entrypoint_parity.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert check_result.evaluator_identity == harness_result.evaluator_identity
assert critical_failure_blocks_task_even_with_high_style_score
assert missing_required_channel.total_score is None
assert structure_only.task_acceptance == "NOT_ASSESSED"
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 关键项失败不能被风格分补偿；关键零权重项失败时即使原始质量100也必须标注任务失败，界面不显示“满分成功”。缺评分通道质量保持null但保留已知维度与已确认失败。file.readable 可作结构分，不作为整项任务充分条件。模型失败、缺来源、缺渲染不能悄悄删权重。相同配置/规格/产物经 Check、Harness、RSI 输出同身份与同判定。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_assessment_entrypoint_parity.py tests/test_artifact_assessment_contracts.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_assessment_entrypoint_parity.py tests/test_artifact_assessment_contracts.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 旧/新分数语义有迁移说明；历史结果不原地改写；规格范围、总分与接受结果不混淆。

**证据：** `T17/<attempt-id>/` 下保存 assessment/parity-matrix.json、score-semantics-v2.md、tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T18：产物问题报告提供可执行的缺陷事实

**阶段/依赖：** D；T12、T14、T17。

**Files：** 修改：`src/workagent_rsi/artifact_verifier.py`、`src/workagent_rsi/assessment_contracts.py`；新增：`tests/test_issue_evidence_quality.py`。

**Interfaces：** 扩展 `ArtifactIssue`：requested_location、observed_locations、failure_origin、affected_requirements、repair_action、verification_steps；兼容原 location/repair_hint。`verify(assessment) -> IssueReport` 仍复用一次 SharedAssessment。

- [ ] **1. 补失败测试。** 在 `tests/test_issue_evidence_quality.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert wrong_total_issue.has_actual_expected_and_location
assert assessment_gap.repair_action.targets_capability
assert no_issue_fabricates_causal_certainty
assert feedback_does_not_contain_internal_answer_knob
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 每个 issue 给出独立期望、实际观察、证据位置、影响和复查项。产物缺陷与检查缺口分开；不可因模型/渲染失败产生“删除错误正文”等修复。以因果关系分组时保留原要求评分，不用字符串相同假装找到同一根因。禁止将 sales_rows=all 等内部答案作为通用反馈；测试替身中的 hint 需明确 qualification_only。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_issue_evidence_quality.py tests/test_artifact_assessment_excel.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_issue_evidence_quality.py tests/test_artifact_assessment_excel.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 典型缺陷不再只有“重新生成”通用建议；真实事实与诊断假设分栏，issue_id 跨同任务同要求稳定。

**证据：** `T18/<attempt-id>/` 下保存 verifier/issue-report-v2-examples.json、feedback-quality-tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T19：从执行轨迹提出可检验原因假设

**阶段/依赖：** D；T03、T18。

**Files：** 新增：`src/workagent_rsi/trace_diagnosis.py`；修改：`src/workagent_rsi/diagnosis.py`、`src/workagent_rsi/rsi_feedback.py`；新增：`tests/test_trace_diagnosis.py`。

**Interfaces：** `diagnose_failure(issue: ArtifactIssue | None, execution: ExecutionOutcome, trace: dict) -> list[FailureDiagnosis]`；输出 evidence_refs、causal_hypothesis、confidence_basis、recommended_action、falsification_check。confidence 未校准时不当概率使用。

- [ ] **1. 补失败测试。** 在 `tests/test_trace_diagnosis.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert syntax_error_hypothesis_cites_script_line
assert range_hypothesis_cites_input_count_and_code_boundary
assert output_only_mismatch_does_not_invent_cause
assert hidden_trace_not_exported
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 先实现可证实的规则：SyntaxError 行号、库 API AttributeError、缺 sheet 的 KeyError、聚合范围漏末行、产物覆盖错误；模型诊断可选，必须引用实际日志/脚本片段。只有输出不一致而无轨迹时允许原因未知。反馈只导出 develop 允许片段，并保留数据与指令边界。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_trace_diagnosis.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_trace_diagnosis.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 每项原因都能被复查或反证；不会把用户数据内容作为系统指令。

**证据：** `T19/<attempt-id>/` 下保存 diagnosis/trace-linked-cases.json、visibility-tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T20：让执行失败进入反馈，环境失败保持独立

**阶段/依赖：** D；T03、T17、T19。

**Files：** 修改：`src/workagent_rsi/workagent_evaluator.py`、`src/workagent_rsi/rsi_loop.py`、`src/workagent_rsi/rsi_feedback.py`、`src/workagent_rsi/workagent_provider.py`；新增：`tests/test_execution_failure_feedback.py`。

**Interfaces：** split report 新增 execution_complete、assessment_complete、execution_success_rate、task_success_rate、quality_denominator；`build_feedback` 接受 develop execution_failures。有效执行失败使任务成功指标为0；无产物质量保持null，不能伪造视觉/语义0分。

- [ ] **1. 补失败测试。** 在 `tests/test_execution_failure_feedback.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert syntax_failure_enters_develop_feedback
assert network_timeout_does_not_become_zero_quality
assert no_artifact_visual_quality_is_none
assert candidate_cannot_win_by_dropping_hard_tasks
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** API不可达/worker缺失停止该真实实验，允许离线任务继续。模型代码错误、漏交付文件、错误 manifest 作为有效 agent_execution 失败进入诊断。跨版本比较必须使用相同入场任务分母，禁止仅挑有产物样本比较质量；含执行失败时以预注册任务成功率为主，质量作相同配对样本的次指标。成功率方案由 T29 门禁消费。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_execution_failure_feedback.py tests/test_rsi_artifact_feedback.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_execution_failure_feedback.py tests/test_rsi_artifact_feedback.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 不再因所有代码错误均被归为评估不完整而失去学习信号；各指标分母与失败归因可追溯。

**证据：** `T20/<attempt-id>/` 下保存 failure-feedback/split-report.json、failure-origin-matrix.json、tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T21：连接生成—检查—修复内循环

**阶段/依赖：** D；T04、T18–T20。

**Files：** 新增：`src/workagent_rsi/repair_loop.py`；修改：`src/workagent_rsi/orchestrator.py`、`src/workagent_rsi/run.py`、`src/workagent_rsi/workagent_office.py`、`src/workagent_rsi/harness.py`；新增：`tests/test_artifact_repair_loop.py`。

**Interfaces：** `RepairPolicy(max_repairs=2, visibility, allowed_artifacts, total_deadline_seconds)`；`RepairLoop.run(task, initial_execution, feedback, execute_repair, assess) -> dict`；Harness.run 接收可选 repair_policy；旧 max_attempts 仍仅表示执行重试，不能偷改含义。

- [ ] **1. 补失败测试。** 在 `tests/test_artifact_repair_loop.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert initial_wrong_artifact_triggers_one_feedback_call
assert successful_repair_has_new_artifact_and_fresh_assessment
assert new_regression_after_local_fix_is_detected
assert inner_repair_does_not_update_skill_registry
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 首次产物失败或代码失败后，生成最小修复请求；保留原任务、当前代码、允许的 issues/诊断和输入摘要，冻结技能/spec。每次修复生成新 attempt 目录和代码哈希，修改当前任务产物，不更新全局技能。不完整环境能力不让模型修改成品。任何修复都复查全部强制要求和源内容保持，避免只修局部引入回退。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_artifact_repair_loop.py tests/test_pipeline_e2e.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_artifact_repair_loop.py tests/test_pipeline_e2e.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 至少一个真实库生成的错误成品，经注入式测试执行器修复后通过；模型调用为 stub 必须明确，不称真实模型闭环。

**证据：** `T21/<attempt-id>/` 下保存 repair-loop/attempt-manifest.json、before-after-reports.json、tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T22：修复预算、保留最佳产物与受保护 split 权限

**阶段/依赖：** D；T21。

**Files：** 修改：`src/workagent_rsi/repair_loop.py`、`src/workagent_rsi/workagent_evaluator.py`、`src/workagent_rsi/workagent_experiment.py`；新增：`tests/test_repair_budget_visibility.py`。

**Interfaces：** `RunBudget(max_model_calls, max_tool_calls, max_repairs, max_wall_seconds, max_cost_usd)`；`FeedbackVisibilityPolicy` 默认只允许 develop 详细验收反馈。所有调用前 reserve，调用后 reconcile。

- [ ] **1. 补失败测试。** 在 `tests/test_repair_budget_visibility.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert total_calls_never_exceed_reserved_budget
assert hidden_expected_not_in_repair_request
assert failed_repair_cannot_replace_best_valid_artifact
assert interrupted_attempt_does_not_erase_history
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 默认最多2次修复；无进展/重复代码与产物状态达到固定阈值后提前停止。保留最佳已验证产物且完整保存被拒修复；中断不覆盖上次有效结果。regression/protected/OOD/final 不向执行器暴露隐藏 expected 或 issues；可运行相同固定的公开自检，但禁止根据保护集判题结果自适应修复。不同实验组预算一致并计入所有重试/修复。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_repair_budget_visibility.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_repair_budget_visibility.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 内循环与外循环的权限和成本明确；任何受保护反馈泄露都使该 cohort 失效。

**证据：** `T22/<attempt-id>/` 下保存 repair-loop/budget-ledger.json、protected-visibility-tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T23：移除题目专属模板并保持通用工具知识

**阶段/依赖：** E；T01、T17、T22。

**Files：** 修改：`src/workagent_rsi/workagent_office.py`、`src/workagent_rsi/prompts/office_agent.md`、`src/workagent_rsi/skill_runtime.py`、`src/workagent_rsi/artifact_candidate.py`；新增：`tests/test_prompt_task_independence.py`、`docs/policies/template-and-overfitting.md`。

**Interfaces：** 正式提示词只由 generic_tool_knowledge、task_instruction、observed_input_manifest、champion_instructions 组成；`execution_mode` 从显式字段/输入决定，不按 benchmark task_id 后缀决定策略。固定 adapter/provider 标记 qualification_only。

- [ ] **1. 补失败测试。** 在 `tests/test_prompt_task_independence.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert changing_task_id_alone_does_not_change_execution_strategy
assert prompt_contains_no_fixture_answer_constants
assert requested_new_slide_is_not_forbidden_in_edit
assert formal_runner_rejects_qualification_only_provider
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 逐项删除固定 Summary答案、120/150/180、固定 Word标题正文、固定三页PPT骨架、edit绝不新增页等。保留“load_workbook用于读取、公式赋值方式”等通用知识。用户明确要求某种模板时允许使用授权模板及来源，不把它作为基准万能解法。正式 runner 拒绝 qualification_only provider；历史 deterministic pilot 只读保留。每项删除先添加任务变体对照，避免盲目删知识导致能力回退。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_prompt_task_independence.py tests/test_simple_harness.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_prompt_task_independence.py tests/test_simple_harness.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 正式路径不再包含已识别题目答案；测试替身和通用模板使用有明确边界；旧pilot保持可读。

**证据：** `T23/<attempt-id>/` 下保存 anti-overfitting/prompt-inventory.csv、removed-fixture-specific-rules.md、tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T24：证明执行依据当前输入而非历史模板

**阶段/依赖：** E；T04、T13、T14、T23。

**Files：** 新增：`src/workagent_rsi/task_observations.py`、`src/workagent_rsi/behavior_probes.py`；修改：`src/workagent_rsi/workagent_office.py`、`src/workagent_rsi/workagent_provider.py`；新增：`tests/test_dynamic_input_behavior.py`。

**Interfaces：** `TaskObservation(input_hashes, inspected_structure, requested_changes, chosen_operations, verification_plan)`；`run_behavior_probes(skill, probe_manifest, executor) -> dict`。计划由当前输入观测支持，不强制统一解题步骤。

- [ ] **1. 补失败测试。** 在 `tests/test_dynamic_input_behavior.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert renamed_sheet_still_uses_actual_input_sheet
assert appended_last_row_changes_total_correctly
assert same_code_with_dynamic_input_can_pass
assert randomized_task_id_does_not_change_answer
assert changing_requested_slide_count_changes_output_count
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 保存真实输入读取/检查调用、生成脚本、工具记录和产物；对同任务改变数值、行列数、sheet名、列顺序、页数和编辑目标。范围/列定位来自观测而非静态常量。代码相同可以合法复用，不以代码hash不同/措辞不同证明动态性；代码静态相似只作告警。任务ID随机化保持问题不变的结果应稳定。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_dynamic_input_behavior.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_dynamic_input_behavior.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 至少每域3组行为探针通过；证据能证明输入变化引起正确输出变化。

**证据：** `T24/<attempt-id>/` 下保存 anti-overfitting/behavior-probe-report.json、generation-trace-index.json；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T25：建立90例独立 evaluator 校准材料

**阶段/依赖：** F；T10–T18、T24。

**Files：** 新增：`tests/fixtures/calibration/case_manifest.json`、`tests/test_calibration_case_integrity.py`；新增：`project_artifacts/phase3_experiments/scripts/build_calibration_cases.py`、`src/workagent_rsi/calibration_data.py`。

**Interfaces：** `CalibrationCase(case_id, domain, source_family, defect_type, oracle_status, expected_locations, expected_scope, source_refs, artifact_hash)`；按 Excel/Word/PPT 各30例：10正确、10单一可控缺陷、5允许等价解、5规格/能力缺口。

- [ ] **1. 补失败测试。** 在 `tests/test_calibration_case_integrity.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert len(cases) == 90
assert per_domain_counts == {"excel":30,"word":30,"powerpoint":30}
assert known_valid_and_invalid_cases_are_independently_labeled
assert every_case_has_artifact_hash_and_truth_source
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 合计90例，使用真实Office库生成可读文件；文件之外保存独立真值。缺陷包含漏末行、错范围、错位、遮挡、源内容破坏；等价解根据自然语言授权；缺口样本不应当成产物坏例。使用不同实现建立 oracle，不能复制 evaluator 算法生成标签。随机种子/输入/产物哈希固定。合成数据声明 project-generated。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_calibration_case_integrity.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_calibration_case_integrity.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 每个类型都有正例与反例；初始90例用于开发校准，不作为最终盲评集，也不声称真实人类一致性。

**证据：** `T25/<attempt-id>/` 下保存 calibration/case_manifest.json、oracle-provenance.json、fixture-integrity-tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T26：按任务家族切分数据并封存最终集

**2026-10-25 用户修订：** Excel、Word、PowerPoint 不再要求数量相等。下面的每域数量是原始方案，后续按实际独立家族制定不同域的配额并分别报告结果；总量目标72基础任务/216实例暂保留。家族隔离、来源证明、输入变体独立性和最终集封存要求继续有效。现有固定配额的原始协议审计仅保留历史对照用途，不能用来否决数量不等本身，也不能据此宣称新配额已完成。

**阶段/依赖：** F；T25。

**Files：** 新增：`src/workagent_rsi/dataset_splits.py`、`tests/test_family_split_isolation.py`；修改：`src/workagent_rsi/workagent_experiment.py`、`project_artifacts/phase3_experiments/data/quality_check.py`；新增：`project_artifacts/phase3_experiments/configs/evaluation_protocol_v2.json`。

**Interfaces：** `TaskFamilyManifest(base_task_id, family_id, source_document_id, variant_ids, domain, split)`；split 为 develop/regression/promotion_validation/final_test/ood_transfer；旧 hidden 通过显式映射转为 promotion_validation，不继续宣称完全未接触测试。

- [ ] **1. 补失败测试。** 在 `tests/test_family_split_isolation.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert family_overlap_between_splits == 0
assert source_document_overlap_between_splits == 0
assert variant_family_never_crosses_splits
assert final_content_not_exported_to_developer_context
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 首批目标60个基础任务：每域20，按8 develop/4 regression/4 promotion_validation/4 final_test分配；每基础任务3个输入变体，共180实例。另设每域4个不同家族OOD基础任务，各3变体，共36实例。合计72基础任务/216实例。家族、源文件、变体整体进入同一split；先分组再生成变体，禁止仅随机按行切分。最终集在评估服务侧封存，只输出哈希和计数，开发/候选容器不可见。若可用独立家族不足，降低声明范围并显式标阻断，不复制改名凑数。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_family_split_isolation.py tests/test_external_dataset.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_family_split_isolation.py tests/test_external_dataset.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 文件哈希冻结之外还具备家族隔离；重复使用的promotion集与一次性final集职责清楚。构造规模是目标，不授权立即运行所有真实调用。

**证据：** `T26/<attempt-id>/` 下保存 data/family-manifest.json、split-quality-report.json、sealed-final-manifest.json；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T27：运行离线校准并衡量误放行/误拒绝

**阶段/依赖：** F；T25、T26。

**Files：** 新增：`src/workagent_rsi/calibration_metrics.py`、`tests/test_calibration_metrics.py`；新增：`project_artifacts/phase3_experiments/scripts/calibrate_evaluator.py`。

**Interfaces：** `calibrate(cases, evaluator_config, output_root) -> CalibrationReport`；报告 confusion matrix、false_accept_rate、false_reject_rate、gap_classification、location_accuracy，以及每类分母和未完成数。

- [ ] **1. 补失败测试。** 在 `tests/test_calibration_metrics.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert known_critical_mutation_false_accepts == 0
assert permitted_equivalent_case_false_rejects == 0
assert all_gap_cases_are_excluded_from_artifact_error_denominator
assert each_aggregate_has_explicit_denominator
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 缺口是单独类别，不作为负样本；PARTIAL按冻结rubric分析。已知确定性关键缺陷集不得漏放行，授权等价解不得因表面形式误拒。输出逐例机器记录与人可读报告；错误例回到负责代码任务修复，不修改真值迎合实现。样本较少时报告计数和区间，不宣称90例证明通用准确率。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_calibration_metrics.py tests/test_review_regressions.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_calibration_metrics.py tests/test_review_regressions.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 所有T01当前范围反例有明确修复或保留缺口；纯确定性部分离线完成。语义/视觉部分待真实能力和人工标注，不用stub填准确率。

**证据：** `T27/<attempt-id>/` 下保存 calibration/calibration-report.json、per-case-results.jsonl、open-gaps.md；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T28：真实语义/视觉判断与人工盲标校准

**阶段/依赖：** F；T16、T27。

**Files：** 新增：`project_artifacts/phase3_experiments/scripts/prepare_human_calibration.py`、`tests/test_human_label_provenance.py`；新增：`src/workagent_rsi/human_calibration.py`。

**Interfaces：** `HumanLabel(case_id, reviewer_id, label, defect_locations, timestamp, evidence_ref)`；`compare_human_labels(labels, decisions) -> dict`。标签源必须为用户/实际审阅者，不允许Codex自签名为人类。

- [ ] **1. 补失败测试。** 在 `tests/test_human_label_provenance.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert missing_human_labels.status == "blocked"
assert labels_do_not_include_model_identity
assert codex_generated_label_not_counted_as_human
assert rubric_changed_requires_new_evaluator_identity
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 先从校准材料抽12例（每域4例，正负和视觉问题均覆盖）给用户核对标准；另准备至少20份与开发家族不同的真实/自然生成成品用于盲标，隐藏模型/版本/分数。先完成人标再揭示judge结果。记录分歧并修订rubric版本，修订后重跑整个可比cohort。关键缺陷误放行则阻止完整质量资格；主观质量报告一致性、误判分母和区间，不用未经验证自报confidence替代。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_human_label_provenance.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_human_label_provenance.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 未获得人类标签时只保留工程资格，不生成“人工一致性通过”；标注与API调用预算均有明确授权后执行。

**证据：** `T28/<attempt-id>/` 下保存 human-calibration/blind-review-pack/、human-labels.jsonl、agreement-report.json；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 需要用户/审阅者实际标注；密钥、模型能力和费用预算需在运行前由用户配置确认。

---

### T29：重复评估、统计晋级与跨批次回归门禁

**阶段/依赖：** G；T09、T20、T22、T26、T27。

**Files：** 修改：`src/workagent_rsi/workagent_evaluator.py`、`src/workagent_rsi/frozen_evaluator.py`、`src/workagent_rsi/rsi_feedback.py`、`src/workagent_rsi/promotion.py`、`src/workagent_rsi/rsi_contracts.py`；新增：`tests/test_statistical_promotion.py`。

**Interfaces：** `ComparisonPolicy(primary_metric, min_effect, paired_resamples=10000, bootstrap_seed=20261016, max_protected_degradation)`；`compare_repeated_runs(baseline, candidate, policy) -> ComparisonReport` 保留每任务每次结果，聚类单位为基础任务家族。

- [ ] **1. 补失败测试。** 在 `tests/test_statistical_promotion.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert all_repeats_are_in_denominator
assert noisy_positive_mean_with_ci_crossing_zero_is_inconclusive
assert critical_regression_blocks_promotion
assert domain_regression_cannot_be_hidden_by_global_mean
assert cached_judgement_is_not_independent_repeat
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 默认独立执行3次，完整保留原始观察，不只取repeat-1。区分执行方差与judge方差；固定相同预算、时间窗口和调用配置并交错baseline/candidate顺序。仅质量可比且所有执行有效时沿用artifact quality主指标：候选减基线>0.05；存在有效执行失败时采用T20任务成功率主指标：增益>0.05，保护域退化不超过0.01。研究晋级要求主效应95%配对cluster-bootstrap下界>0；样本不足/区间跨0为inconclusive，不篡改阈值。安全/关键回归必须为0；每域单独报告，不以Excel收益抵消Word退化。工程smoke可以完成但不得据小样本正式晋级。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_statistical_promotion.py tests/test_promotion.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_statistical_promotion.py tests/test_promotion.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 研究门禁与工程资格分开；阈值预注册，所有随机种子实际用于本地重采样；模型API不支持seed时记录not_supported，不宣称可确定复现。

**证据：** `T29/<attempt-id>/` 下保存 promotion/statistical-policy.json、paired-comparison.json、gate-tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T30：经验记忆、回归集、版本与恢复身份

**阶段/依赖：** G；T06、T08、T09、T29。

**Files：** 修改：`src/workagent_rsi/registry.py`、`src/workagent_rsi/rsi_loop.py`、`src/workagent_rsi/workagent_experiment.py`、`src/workagent_rsi/costs.py`；新增：`tests/test_rsi_identity_and_memory.py`。

**Interfaces：** `LessonRecord(source_split, evidence_refs, generalized_rule, failure_class, applicability, excluded_values)`；negative-evidence键包含parent_hash/cohort_hash/patch_hash；resume manifest包含provider端点与配置、技能/spec/evaluator、隔离镜像、预算和已完成attempt身份。runner新增显式resume入口。

- [ ] **1. 补失败测试。** 在 `tests/test_rsi_identity_and_memory.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert new_parent_does_not_inherit_invalid_global_pruning
assert same_rejected_patch_in_same_cohort_is_pruned
assert changed_candidate_endpoint_refuses_resume
assert completed_attempt_is_not_reexecuted_or_overwritten
assert skill_package_version_matches_registry_version
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 从develop错误抽象出通用规则并保存公开记忆；禁止把隐藏值、文件名答案映射和保护集诊断写入记忆。已有负面patch只有相同parent/cohort下才剪枝，不能永久禁止在新父版本重试。checkpoint保存全部attempt；实际provider/model变更必须新实验或显式fork，不伪装原run恢复。注册包的逻辑版本与registry记录一致；记录所有失败API调用、重试、工具、修复和时间；成本缺失不得零填。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_rsi_identity_and_memory.py tests/test_multiround_rsi.py tests/test_registry.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_rsi_identity_and_memory.py tests/test_multiround_rsi.py tests/test_registry.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 当前公开runner能恢复中断；历史证据追加不覆写；champion变化、回滚和public lessons来源完整。

**证据：** `T30/<attempt-id>/` 下保存 rsi/resume-identity.json、lesson-provenance.json、negative-evidence-tests.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T31：真实三域资格：失败—修复—复评及外循环

**阶段/依赖：** G；T04–T30中对应门禁，尤其G1/G2/G3；T28未完则仅允许声明结构/确定性资格。

**Files：** 新增：`project_artifacts/phase3_experiments/scripts/run_qualification_v2.py`、`project_artifacts/phase3_experiments/configs/live_qualification_v2.json`、`tests/test_qualification_entrypoint.py`。

**Interfaces：** 命令支持 `--dry-run`、`--config PATH`、`--resume RUN_ROOT`；配置必须显式 model/provider/endpoint、已验证能力、sandbox digest、budget、allow_live_calls；默认allow_live_calls=false。

- [ ] **1. 补失败测试。** 在 `tests/test_qualification_entrypoint.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert dry_run_makes_zero_network_calls
assert live_requires_explicit_budget_and_capability
assert all_three_domains_have_real_artifacts
assert rejection_keeps_champion_unchanged
assert missing_judge_cannot_claim_full_quality_qualification
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 先用stub验证流程，再dry-run输出调用上界和预计预算。真实资格每域至少一个自然发生的失败案例，保存初始代码/产物、issues、修复请求和复评；不能人为制造baseline失败再称真实收益。若所有任务自然满分，可完成管线资格，但要另选开发侧适当难度任务并冻结新cohort。外循环四个非空split每个覆盖三域，首轮只验证候选生成、拒绝/保留、checkpoint和证据链；不要求必须接受。失败API原记录保留；换模型作为新分支cohort。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_qualification_entrypoint.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_qualification_entrypoint.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 可重放证据包完整；只报告实际完成范围。真实修复未发生时状态incomplete，不用单纯正确生成代替修复验证。

**证据：** `T31/<attempt-id>/` 下保存 qualification/run-manifest.json、call-budget.json、three-domain-repair-report.md、outer-loop-summary.json；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 真实API付费调用须用户已配置预算上限并启用；无密钥/无能力停止真实运行，不输出或代填密钥。

---

### T32：同预算对照与多轮RSI有效性实验

**阶段/依赖：** H；T26、T28、T29–T31。

**Files：** 新增：`project_artifacts/phase3_experiments/configs/rsi_comparison_v2.json`、`project_artifacts/phase3_experiments/scripts/run_comparison_v2.py`、`tests/test_experiment_budget_fairness.py`。

**Interfaces：** 四组：B0固定技能单次；B1固定技能同任务修复/重试；B2单轮技能优化；B3多轮RSI。总调用/token/时间预算字段明确；`prepare_experiment(config) -> FrozenExperimentManifest`，先冻结后运行。

- [ ] **1. 补失败测试。** 在 `tests/test_experiment_budget_fairness.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert compared_arms_have_equal_declared_budget_caps
assert optimizer_and_failed_calls_are_charged
assert final_test_used_once_after_selection
assert no_statistical_gain_is_reported_as_no_gain
assert baseline_champion_and_final_champion_are_both_reassessed_on_fixed_reference
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** B1/B2/B3总资源上限相同，优化、失败重试、内修复及评估成本都计入；B0明确报告实际较低成本，不宣称等成本优势。B3先3轮pilot；只有预算足够且无边界违规再扩至6轮，编辑预算上限[3,3,2,2,1,1]但当前只有instructions一个字段，禁止用重复覆盖凑edit数。按基础任务家族报告成功率、关键缺陷、修复收益、迁移、方差、成本；同时显示学习曲线和与起始版本的固定参考集配对。结束后一次性调用封存final；若根据final改方案，必须使用新的未接触测试集。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_experiment_budget_fairness.py tests/test_result_cohorts.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_experiment_budget_fairness.py tests/test_result_cohorts.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** RSI优于重试的结论必须来自真实模型对照与区间，不由deterministic策略预设；负结果同样完整交付。预算不足时缩减预注册设计并冻结新manifest，不能只运行有利组。

**证据：** `T32/<attempt-id>/` 下保存 study/pre-registered-manifest.json、per-task-results.jsonl、learning-curves.csv、comparison-report.md；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 预计真实总成本超用户批准上限时先停；样本量不足不得用工程资格结果替代研究结论。

---

### T33：外部数据入场与基准原生评分兼容

**阶段/依赖：** H；T09、T26、T32。

**Files：** 修改：`project_artifacts/phase3_experiments/data/external/source_manifest.json`、`project_artifacts/phase3_experiments/scripts/quality_check_external.py`、`project_artifacts/phase3_experiments/scripts/run_formal.py`；新增：`tests/test_external_protocol_v2.py`。

**Interfaces：** `ExternalAdmissionReport(source_version, code_license, data_license_scope, provenance, checksums, native_evaluator_identity, boundary)`；外部原生评分与自定义质量指标分开输出，禁止将修改版指标作为原benchmark结果。

- [ ] **1. 补失败测试。** 在 `tests/test_external_protocol_v2.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert missing_data_admission_blocks_formal
assert answer_workbook_not_visible_to_agent
assert custom_quality_not_labeled_native_benchmark_score
assert official_evaluator_version_is_recorded
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 复核官方来源、实际数据许可范围、版本与checksum；区分已确认缺失和仅待验证，不无限重复旧审查也不擅自作法律保证。模型只获得任务允许输入，参考答案/原生评分器位于评估侧。先少量验证官方评分一致性，再按批准预算扩展；改配方/模型/协议创建新cohort。无法确认来源/许可或需要用户判断时阻断外部正式实验，已完成自建工程工作照常交付。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_external_protocol_v2.py tests/test_external_dataset.py tests/test_formal_runner.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_external_protocol_v2.py tests/test_external_dataset.py tests/test_formal_runner.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 外部声明与项目自建结果完全分开；不保证一定能准入，明确真实阻断项及责任人。

**证据：** `T33/<attempt-id>/` 下保存 external/admission-report.json、native-evaluator-parity.json、formal-claim-boundary.md；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 许可/来源不明确、账户或数据访问需用户提供时请求用户；禁止绕过门禁。

---

### T34：全量验收、跨平台检查与证据重放

**阶段/依赖：** H；T00–T33，允许有明确外部阻断但不能标全部完成。

**Files：** 新增：`project_artifacts/phase3_experiments/scripts/validate_release_v2.py`、`tests/test_release_claims.py`；修改：`project_artifacts/execution_log.md`、`project_artifacts/artifact_manifest.md`。

**Interfaces：** `validate_release(manifest: Path) -> ReleaseGateReport`；分级 engineering_pass/live_loop_pass/research_pass/external_pass，不能只有一个笼统completed。

- [ ] **1. 补失败测试。** 在 `tests/test_release_claims.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert claim_levels_reflect_actual_evidence
assert blocked_human_or_external_gate_prevents_research_or_external_pass
assert moved_bundle_replay_preserves_assessment_identity
assert complete_test_suite_has_no_unexplained_failures
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 运行完整pytest、compileall、diff check、90例校准和T01反例；验证bundle换目录后可解析、哈希完整、评估重放不重用过期分数。Windows为用户主要执行环境，Linux检查覆盖非COM逻辑；不可用平台不伪称验证通过。真实测试明确 integration标记，不通过网络可用性测试偷跑付费调用。扫描已跟踪文件中的凭据模式并只报路径/规则，不打印值。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_release_claims.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_release_claims.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 所有未完成项有状态和证据；真实报告不引用当前不可获取的Windows绝对路径作为唯一证据；最终代码差异可审查。

**证据：** `T34/<attempt-id>/` 下保存 release/release-gate.json、full-pytest.txt、replay-check.json、coverage-map.json；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---

### T35：交接文档、回滚点与用户执行入口

**阶段/依赖：** H；T34。

**Files：** 修改：`README.md`、`src/workagent_rsi/README.md`、`Agent.md`、`skills/office-artifact-evaluator/SKILL.md`、`skills/office-artifact-verifier/SKILL.md`及相关references；新增：`docs/operations/evaluation-rsi-v2.md`、`tests/test_documented_entrypoints.py`。

**Interfaces：** 用户入口保持Harness；文档分别给单任务、修复、校准、资格、比较和formal命令，全部指向实际已实现入口。保留完整旧格式读取，新增迁移/回滚说明。

- [ ] **1. 补失败测试。** 在 `tests/test_documented_entrypoints.py` 及列出的测试文件落实下面的断言契约；使用独立fixture，不依赖实现返回值构造真值。

```python
assert documented_commands_accept_help_or_dry_run
assert dry_run_has_zero_paid_calls
assert rollback_preserves_all_run_evidence
assert docs_do_not_claim_unexecuted_human_or_external_validation
```

- [ ] **2. 运行红灯并留证。** 执行下方命令；确认失败指向本task行为缺口，不把缺依赖等环境错误冒充功能红灯。
- [ ] **3. 实现本task。** 用中文说明评分范围、三个覆盖口径、失败归因、模板边界、内外循环和声明等级。更新Agent.md过时状态时保留历史事实，不把旧报告升级为新结果。记录每阶段commit、兼容变化、回滚命令与数据快照，回滚只切换代码/alias不删除证据。文档命令用--help/--dry-run实际验证。每阶段本地commit；不得默认push/PR/merge。
- [ ] **4. 运行绿灯和差异审查。** 使用同一命令，期望所属用例PASS；尚需真实环境/人工输入的部分独立标blocked，不能用stub结果代替。

```powershell
& $TaskPython -m pytest -q tests/test_documented_entrypoints.py
```

Bash使用：`"$TASK_PYTHON" -m pytest -q tests/test_documented_entrypoints.py`。

- [ ] **5. 记录并本地提交。** 运行 `git diff --check`；明确加入本task源文件和测试后commit；更新task-ledger与execution_log。T01以红灯基线为其交付，不要求在该task修复所有反例。

**验收标准：** 用户可以从未完成task继续；最终交接列完成/阻断/未开始、可用能力、证据路径和下一步，不承诺尚未证实的效果。

**证据：** `T35/<attempt-id>/` 下保存 handoff/final-status.md、task-ledger.json、rollback-points.json、commands-verified.txt；实际命令、退出码、输入/输出哈希和commit引用必备。

**人工介入/阻断：** 无额外人工审批；遵守全局中断规则。

---


## 5. 覆盖映射与验收检查表

| 审查发现/要求 | 负责task | 不能采用的捷径 |
|---|---|---|
| API候选未见champion、历史不继承 | T06/T30 | 仅传parent_version字符串 |
| run_python宿主执行、密钥/保护集可见 | T04/T05 | 只加提示词或路径黑名单 |
| patch归一化截断违规项 | T07/T08 | 删掉违规后接受剩余项 |
| pilot/formal或跨版本指标混合 | T09/T29 | 同名字段直接mean |
| Python启动器与旧fixture失败 | T02 | 降阈值或改成永远通过 |
| 自然语言需求未进入spec | T10/T11/T17 | file.readable=任务成功 |
| 文本错位、隐藏文字、视觉缺口 | T12/T15/T16 | 全文contains/几何推测替代视觉 |
| 公式字符串、缓存与真实重算混淆 | T13 | 写入假缓存/仅比较同一输入值 |
| 编辑损坏源文件 | T14 | 一概禁止新增对象或只验目标单元格 |
| verifier通用建议、无诊断 | T18/T19 | 模型凭输出编造确定根因 |
| 执行失败无法学习 | T20 | 所有无产物都当环境缺失或都补0分 |
| 最终评估失败不修复 | T21/T22 | 无限重试/隐藏预期泄露 |
| 固定模板/答案/确定性替身证明收益 | T23/T24/T32 | 看代码不同就声称动态Agent |
| 63测试通过但漏判缺陷 | T25/T27/T28 | 照着检查实现生成真值 |
| 同家族切分、重复hidden选择 | T26/T32 | 仅改task_id或随机按行切分 |
| repeat-1评分、缓存伪独立 | T16/T29 | 选最好一次/只看均值 |
| 模型切换/恢复/负面剪枝不适配新父版 | T30 | 修改旧记录或全局永久剪枝 |
| 绝对路径证据不可复核 | T03/T31/T34 | 只交中文报告不交原始记录 |
| 外部来源和正式结论 | T33/T34 | 用pilot/自定义分数冒充原benchmark |

### 完成条件

- [ ] 36个task均有completed/blocked/not_started等真实状态，不把blocked当完成。
- [ ] T01反例及其所有者映射齐备；新断言确实先红后绿。
- [ ] 全量pytest无未解释失败；平台/依赖skip有原因且不冒充相关能力通过。
- [ ] 生成代码真实隔离、环境净化和子进程清理通过本机探针。
- [ ] evaluator的需求覆盖、检查完成、证据范围分开；空白或错位/不可见产物不能获完整任务通过。
- [ ] verifier输出实际证据、诊断假设和可复查修复动作；当前任务修复链真正调用。
- [ ] 90例校准、输入变体和家族隔离报告齐备；真实人标若缺失，研究资格明确blocked。
- [ ] baseline/candidate保存全部repeat，晋级不掩盖域回退和随机波动。
- [ ] 当前champion、拒绝候选、公开经验、负面证据、恢复与回滚可追溯。
- [ ] 真实模型修复、RSI收益、外部结果分别有对应证据，结论可以是“无显著收益”。
- [ ] 所有交付路径相对可重放，原始记录脱敏；没有密钥、保护答案进入候选上下文。

## 6. 给本地Codex的启动提示词

```text
请执行 docs/superpowers/plans/2026-10-16-evaluation-rsi-hardening.md。

先完整读取计划、第2节设计约束以及仓库当前AGENTS.md/Agent.md，
从T00检查真实本机状态，不假设与审查基线完全一致。

本次目标是按计划逐task实施并验证，不是再写一个泛化方案。
使用executing-plans技能，默认串行；我未要求启用子代理。
先保护用户已有改动，必要时用独立worktree/分支，不做破坏性reset。

每个task先补明确失败测试、保留红灯证据、实现最小变更、运行对应检查，
保存实际日志和证据并更新task账本，再进入下一task。
不要为了通过样例增加固定答案、task_id分支、固定模板或降低判题标准。

完成已授权的离线代码/测试/文档工作无需逐项找我确认。
只有需要真实凭据、系统安装或Officeworker、任务澄清、人工标签、
付费预算或外部发布时及时告知缺项和具体动作，相关task标blocked；
继续其他不依赖它的工作，不伪造成功。

真实API默认关闭。任何付费实验先dry-run给出资源上界；
只有live_call_policy具备我明确批准的具体预算和配置时才开始。
不使用Ollama跑本轮真实实验；不默认push、开PR、merge或部署。

每阶段给我：完成task、真实测试、证据目录、阻断项和下一步。
工程通过、真实模型闭环通过、研究有效、外部benchmark通过分别报告。
```

### 中断后的续跑提示词

```text
继续执行同一计划。先读取task-ledger、execution_log和最新证据manifest，
核对git/输入/技能/spec/evaluator/provider/sandbox/budget身份。
只恢复未完成task或attempt，不重复运行已完成真实调用，不覆盖失败记录。
发现身份改变则明确fork新cohort或重新冻结，不修改旧checkpoint欺骗恢复检查。
保留已有批准预算，不能因恢复而重置计数或追加费用。
```

## 7. 输出目录、提交与回滚约定

```text
docs/superpowers/specs/2026-10-16-evaluation-rsi-hardening-design.md
docs/superpowers/plans/2026-10-16-evaluation-rsi-hardening.md
docs/operations/evaluation-rsi-v2.md
project_artifacts/results/hardening-v2/
  task-ledger.json
  T00/<attempt-id>/...
  T01/<attempt-id>/...
  ...
  T35/<attempt-id>/...
```

task-ledger每项记录：id、status、depends、起止时间、base/完成commit、命令引用、退出码、证据manifest、阻断原因、下一动作。命令日志不复制环境变量全集。

每阶段保留可回滚commit与registry alias快照；回滚代码使用用户可审查的分支/提交操作，回滚技能通过registry记录完成。禁止删除失败artifact、历史数据或强制覆盖已发布证据。

代码仓库只跟踪脱敏manifest、必要小型样例与文档；大产物在用户选择的持久位置保存，并在manifest记录获取方式和哈希。没有实际可取地址时写unavailable，不能以原电脑绝对路径假装可重放。

## 8. 资料索引

- 审查仓库固定版本：https://github.com/fisher-yu-like/workagent-rsi/tree/43f89d54daed37aba9f0e79a7df79b3288b2f993
- SharedAssessment与规格适配：`src/workagent_rsi/artifact_assessment.py`
- 评分与缺陷报告：`src/workagent_rsi/artifact_evaluator.py`、`src/workagent_rsi/artifact_verifier.py`
- 候选验证：`src/workagent_rsi/verifier.py`、`src/workagent_rsi/candidate_provider.py`
- 冻结评估与RSI：`src/workagent_rsi/workagent_evaluator.py`、`src/workagent_rsi/rsi_loop.py`、`src/workagent_rsi/rsi_feedback.py`
- 汇总脚本：`project_artifacts/phase3_experiments/scripts/analyze_formal.py`
- 官方多输入与重算参考：https://github.com/RUCKBReasoning/SpreadsheetBench （借鉴协议；数据入场另按T33核验）
- Office任务分类型评分参考：https://github.com/zlwang-cs/OfficeBench （精确、模糊与执行评分按任务选用）

本计划不保证修复后必然出现RSI收益；它保证收益、退化、无效和环境阻断都有可检验的判断流程。执行时若新证据推翻审查发现，应记录反证并调整该task，禁止照计划机械修改已经正确的代码。
