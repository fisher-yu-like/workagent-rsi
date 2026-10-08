# WorkAgent-RSI 阶段执行日志

> 这份日志用人类能直接理解的语言记录自动执行过程。每次更新保留实际证据、状态和下一步；没有执行的内容不会写成已完成。

## 当前状态

- 总体状态：执行中
- 当前阶段：阶段 4：外部数据门禁与正式实验入口
- 当前任务：metadata-only 来源门禁已通过；正式模式已验证会拒绝未获准数据，正在整理阶段证据并准备下一阶段的真实许可核验
- 自动批准：已收到，后续按计划自动推进；阶段失败时停止并记录原因
- 结果根目录：`project_artifacts/results/`
- 分支：`codex/closed-loop-rsi`

## 阶段 0：基线冻结

- 状态：通过，提交 `653066a`
- `61 passed`，`compileall` 通过，pilot 数据质量检查 14 项全部通过。
- 已记录 Python 3.12.10、依赖、Codex/Ollama、Office 16.0 COM、LibreOffice 不可用和外部 WorkAgent 未配置。
- 已创建 `formal_study/contract.json`、`capability_matrix.json`、`baseline_manifest.json`。
- 30 条任务被明确标为 project-generated pilot，不作为外部 benchmark 或正式主结果。

## 阶段 1：真实 Office provider

- 状态：通过，代码提交 `3de1ecd3c3ce28f3e6f0ea50b811bb6ce58fd04a`。
- COM provider 对 25 条公开任务完成 25/25，平均自动分数 1.0，覆盖 Excel、Word、PowerPoint。
- 两次中断运行及资源泄漏原因已保留；最终运行结束后新增 automation Office 进程为 0。
- 证据：`project_artifacts/formal_study/stage1_manifest.json`。

## 阶段 2：Office 文件级 evaluator v2

### 实现与红绿测试

- 红测试先因缺少 `workagent_rsi.office_checks` 正确失败。
- 已实现 `office_checks.py`：OOXML 包、文件 hash、Excel 工作表/单元格/公式、Word 标题/样式/OOXML、PowerPoint 文本/页数/几何。
- 已实现 `render_checks.py`：PPT 对象重叠、越界、空白页；像素渲染器不可用时记录 `rendering: unavailable`，不转换成分数。
- `OfficeArtifactEvaluator` 已升级为 `office-evaluator-v2`，报告含 dimensions、warnings、channel status、artifact/evaluator hash 和 evidence。
- `FrozenEvaluator` 现在保存每个任务的维度、警告、通道状态和证据。

### Gate 证据

- 代码提交：`ab37c71aa00f288f9a6f5be2b708007e9f405189`。
- 全量测试：`71 passed in 55.29s`（包含阶段 3 新增测试；阶段 2 单独验证为 69 passed）。
- `compileall` 退出码 0，`git diff --check` 退出码 0。
- evaluator 三域验证：`project_artifacts/results/qualification/evaluator-v2/20260927T143324Z/validation.json`，Excel/Word/PowerPoint 全部通过；PowerPoint 像素渲染通道明确为 unavailable。
- COM qualification：`project_artifacts/results/qualification/real-office/20260927T142641Z/`，25/25 成功、0 失败、平均自动分数 1.0、Office 16.0 重开通过；EXCEL、WINWORD、POWERPNT automation 进程均为 0，运行时 `git_worktree_dirty=false`。
- 阶段 manifest：`project_artifacts/formal_study/stage2_manifest.json`。
- Gate 结论：通过，已自动进入阶段 3。

## 阶段 3：六轮 RSI

### 已完成的代码工作

- `RSILoop.run()` 已增加，默认编辑预算为 `[3, 3, 2, 2, 1, 1]`；旧 `run_round()` 保留兼容。
- 每轮保存 champion baseline、candidate diff、diagnosis、provider record、verification、split reports、decision、rollback point 和继承的 evidence refs。
- 每轮开始会从 registry 当前 champion 生成只读 `source_snapshots/round-*`，所以后续候选实际读取上一轮批准的 `skill.json`，而不是只看到旧 source 或反馈文本。
- 每轮写 `round_summary.json` 和 `cost.json`；token/tool/step/render 无 provider 能力时标为 unavailable，wall time 和磁盘大小单独记录。
- `checkpoint.json` 保存 contract、dataset split、evaluator、provider、model、代码 hash；resume 会校验身份，已完成轮次不会重新评分。
- registry 增加 `negative_evidence` 表；被拒绝候选会记录 patch hash，重复候选会被剪枝，不会无限重复。
- `ExperimentRunner` 和 E01-E12 入口默认使用六轮协议，仍可通过 `--rounds` 调整。

### 当前验证

- 阶段 3 红测试先因 `RSILoop.run` 不存在而失败。
- 实现后阶段 3 相关测试和旧 RSI 测试：`4 passed`；加入中断恢复和继承性测试后，全量回归：`72 passed in 59.66s`。
- `compileall` 通过；真实六轮 pilot 已完成，正在写阶段 3 Gate manifest。

### 阶段 3 Gate：通过（2026-09-27）

- 代码提交：`312a61caa447af91eafe9180ffa5d183f7166759`，qualification 运行时工作树干净。
- deterministic E05 六轮结果：`project_artifacts/results/qualification/multiround-final/E05/20260927T150924352814Z-deterministic-e05/`。
- 预算为 `[3, 3, 2, 2, 1, 1]`；第 1 轮 `0.1.0 -> 0.2.0` 被接受，第 2 轮被拒绝，后 4 轮由 registry 负证据剪枝；develop 分数 `0.0 -> 1.0`。
- 每轮都有 `round_summary.json` 和 `cost.json`，token/tool/step/render 通道在 deterministic provider 下明确标为 unavailable，wall time 与磁盘大小可用。
- 中断恢复测试确认已完成轮不重新评分，未完成轮使用 retry 目录恢复，并读取上一轮 champion 的 `required_text` 包。
- 阶段 manifest：`project_artifacts/formal_study/stage3_manifest.json`。
- 阶段 3 Gate：通过，已自动进入外部数据来源、许可证和质量门禁；当前只做 metadata/adaptor，不把未核实数据写入正式结果。

## 阶段 4：外部数据来源与许可门禁

- 当前状态：进行中。
- 目标是先记录 OfficeBench、SpreadsheetBench、OSWorld/Windows Agent Arena 等候选的官方来源、版本和许可状态；许可证未核实前不下载任务文件。

### 阶段 4 当前证据（2026-09-27）

- 已创建 `data/external/source_manifest.json`、`source_verification.json`、`dataset_card.md`、metadata-only intake 和质量检查脚本。
- 官方核验记录：OfficeBench 仓库 Apache-2.0 但数据许可证未单独声明；SpreadsheetBench README 声明 CC BY-SA 4.0，官方 `main` commit 为 `49b73a94775fb489063f60ca1865e3a650079a79`，sample archive 为 19,936,871 bytes、Git blob SHA `4ff8918668c2876f1d6b6d17845a4fe76e57ef52`；OSWorld 仓库 Apache-2.0 但 VM/资产条款待核；Windows Agent Arena 仓库 MIT 但 Windows/Office 资产条款待核；SpreadsheetBench-2 未发现 license metadata。
- `quality_check_external.py`：metadata-only 质量门禁通过，所有候选下载状态为 `metadata_only`，当前正式数据选择为 `null`。
- `fetch_external_data.py` 默认只写 intake metadata；没有同时满足数据许可证、checksum 和明确确认时会拒绝下载。
- 阶段 4 尚未通过正式数据 Gate：目前没有外部任务文件进入 `raw/`，这不是正式 benchmark 结果。

### 阶段 4 执行入口与验证（2026-09-27）

- 新增 `configs/formal_matrix.json` 和 `configs/baselines.json`：明确 pilot、formal、六个实验臂、固定种子、重复次数和 claim boundary；配置文件不预填任何分数。
- 新增 `scripts/run_formal.py`：`--mode formal` 在创建结果目录前执行来源、许可、checksum、质量报告和五个 split 文件门禁；当前命令因 `formal_dataset_selected=null` 正确退出码 2，没有生成 formal 结果。
- `--mode pilot --provider deterministic --experiments E01` 已完成一次可审计 pilot，结果位于 `project_artifacts/results/qualification/formal-pilot/stage4-pilot-e01/`；数据类型明确为 `project-generated`，`external_benchmark=false`，不能作为外部 benchmark 结论。
- 新增 `scripts/analyze_formal.py`：只聚合 `completed` 实验，`unavailable/timeout` 不转成分数；上述 pilot 分析写入同一结果目录的 `analysis.json`，claims_allowed 为 `false`。
- 下载器已升级为临时文件 + SHA-256 校验 + 原子改名；当前 manifest 没有满足 `verified license + checksum` 的候选，因此没有下载任何外部文件。
- 阶段 4 新增测试覆盖：正式门禁拒绝、pilot claim boundary、不可用结果不计分、checksum 成功/失败、外部文件边界。

### 阶段 4 Gate 记录（2026-09-28）

- 代码提交：`5aeb601aee5fdb21a0cb1654ac6b4fdf004633dd`，提交前工作树干净。
- 全量回归：`82 passed in 73.37s`；`compileall` 和 `git diff --check` 通过。
- 干净提交上的 metadata checker：pass；候选 5 个，`formal_dataset_selected=null`，没有外部文件进入 `raw/`、`processed/` 或 formal results。
- 干净提交上的 formal 命令在结果目录创建前 fail-closed；原因是正式数据未选择、manifest 仍为 `metadata_only`、五个正式 split 不存在。这个非零退出是预期安全行为，不是实验失败分数。
- 干净提交上的 pilot E01：`project_artifacts/results/qualification/formal-pilot/stage4-pilot-e01-clean/`，deterministic provider，状态 completed；分析器只记录实际 `task_success_rate=0.0`，并将 `claims_allowed=false`。它是项目生成 fixture 的工程验证，不是外部 benchmark 结果。
- 阶段清单：`project_artifacts/formal_study/stage4_manifest.json`。
- 阶段 4 Gate：metadata-only 子门禁通过；正式数据 Gate 尚未通过，自动进入 workbook 级许可、来源和泄漏审查，不下载未核实数据。
- 2026-09-28 的来源复核修正了 SpreadsheetBench 官方 archive 文件名，并补录 README blob `d5ae034cb14d8da4733cfc5f38a067eee792aef9`、full archive blob `b4583957c7838204bb45c1a7af35d3581e7e8fb3`、Verified subset blob `b6baaf0f23ef5adc1cd22078f4eeb3102b4a7c72`；对应 metadata revision 为 `919939b8a4a09cb62be644227a5c93cc20c50172`。README 的项目级 CC BY-SA 4.0 声明仍不足以清除论坛来源 workbook 和 answer 文件的逐文件权利，因此状态仍为 `conditional_review_required`。
- 随后将 manifest 的下载地址修正为官方 raw 内容 URL `https://raw.githubusercontent.com/RUCKBReasoning/SpreadsheetBench/main/data/spreadsheetbench_912_v0.1.tar.gz`，并让质量检查在通过时输出 `manifest_version: present`；对应 metadata revision 为 `aeb462e4eaa801496d0b0fd937a0c46c54295234`。这仍只保存 metadata，没有下载 archive。
- 完整 deterministic pilot matrix 已在干净提交上完成：`project_artifacts/results/qualification/formal-pilot/stage4-pilot-matrix-20260928b/`，E01/E02/E05/E07/E08 全部完成（6/6，0 unavailable/timeout，0 failed）。分析器输出 `claims_allowed=false`；E05 develop 为 `0.0 -> 1.0`，E08 transfer delta 为 `-1.0`，仅作为本地 fixture 的机制/跨域工程信号。

### GitHub 同步（2026-09-28）

- 分支 `codex/closed-loop-rsi` 已推送到 `origin`；本次阶段日志最终提交为 `de6bdb8eb4375f3d902b15952aac3c9623884e64`，远程与本地一致。

## 下一步

1. 提交阶段 4 metadata-only 门禁、正式矩阵、guarded runner 和分析器，并记录完整测试证据。
2. 继续核验 SpreadsheetBench workbook 级来源和许可；在 `verified + checksum + quality + leakage` 全部满足前，保持 formal runner 拒绝。
3. 只有外部数据 Gate 通过后，才下载官方 archive、生成 raw/interim/processed 层并运行 formal matrix；否则继续进行不带外部 benchmark 声明的 pilot/工程验证。

## 阶段 5：真实模型 RSI pilot（2026-09-28）

- 状态：运行中。
- 运行范围：项目生成的 pilot fixture，实验 `E05`，六轮 RSI；这是真实 Codex/Ollama 候选生成，不是模型权重训练，也不是外部 benchmark。
- Provider：Codex CLI `0.157.1`，本地 Ollama `qwen2.5:7b`；结果根目录为 `project_artifacts/results/qualification/real-model/`。
- 启动命令：`py -3.12 project_artifacts/phase3_experiments/scripts/run_formal.py --mode pilot --provider codex --experiments E05`。
- 当前尚未写入分数；每轮完成后追加 provider、checkpoint、cost、验证、晋级和 claim boundary 证据。
- 首次 invocation `real-e05-qwen25-20260928` 已结束但状态为 `unavailable`，根因是 Windows GBK 解码 Codex UTF-8 输出时触发 `UnicodeDecodeError`，不是模型评分；失败证据保留在同名结果目录。已增加显式 UTF-8、`errors=replace` 的 provider 回归测试，准备从新 invocation 重试。
- `retry1` 仍为 `unavailable`，根因是相对 `--output-last-message` 路径在 candidate workspace 下无法创建；已增加相对 `record_root` 回归测试并统一解析绝对路径。
- `retry2` 已真实生成并验证前 5 轮，但在第 6 轮暴露 registry 版本冲突：多个不同的 rejected sibling 都从 `0.2.0` champion 计算出 `0.3.0`。已增加版本分配回归测试，改为由 registry 为每个候选分配单调唯一版本，准备再次运行。
- `retry3` 已完成完整六轮，结果状态为 `completed`，6/6 provider records 为 completed，1 个候选被接受、5 个被拒绝，develop 从 `0.0` 提升到 `1.0`；第 4 至 6 轮的无效 patch 被 verifier 拒绝，未转成成功分数。结果目录为 `project_artifacts/results/qualification/real-model/real-e05-qwen25-20260928-retry3/`。
- 核验发现模型可能在结构化 JSON 中自报错误的 model identity；下一次结果会记录命令配置的 `ollama:qwen2.5:7b`，不再信任候选字段中的自报值。

### 阶段 5 追加记录（2026-09-28）

- `real-e05-qwen25-20260928-final` 已保留为真实失败证据：第 1、2 轮 provider 完成，第 3 轮返回的结构化候选缺少 `atomic_edits[0].hypothesis` 和 `atomic_edits[0].expected_metric`，`CandidatePatch` 校验拒绝，运行状态为 `unavailable`；该目录不计入分数，不作为成功运行。
- `real-e05-qwen25-20260928-final-retry1` 已启动，继续执行六轮 E05；结果仍属于 `project-generated` pilot，不是 external benchmark 或模型权重训练。
- 重试前验证（2026-09-28）：`py -3.12 -m pytest -q --basetemp=.pytest-stage5-final` 为 `86 passed in 44.24s`；`compileall` 退出码 0；`git diff --check` 退出码 0。

### 阶段 5 真实模型 pilot 完成（2026-09-28）

- `real-e05-qwen25-20260928-final-retry1` 正常完成六轮，顶层状态为 `completed`，6/6 provider records 为 `completed`。
- Provider 为 Codex CLI `0.158.0-alpha.2.1` + Ollama `qwen2.5:7b`；checkpoint 固定记录 `model_identity=ollama:qwen2.5:7b`，不信任模型输出中的自报身份。
- 第 1 轮接受候选，`0.1.0 -> 0.2.0`；第 2、5 轮无额外 develop gain 被拒绝；第 3、4、6 轮因非法 patch JSON 被 verifier 拒绝。最终 develop 为 `0.0 -> 1.0`，accepted=1、rejected=5、unavailable=0。
- 机器分析已写入 `project_artifacts/results/qualification/real-model/real-e05-qwen25-20260928-final-retry1/analysis.json`；其 `claims_allowed=false`，`pilot_is_not_external_benchmark=true`，`unavailable_is_not_a_score=true`。
- 六轮成本文件已保存 wall time 与 disk bytes；token、tool call、step、render 通道明确为 `unavailable`，未被转换为分数或零成本。
- 阶段 manifest：`project_artifacts/formal_study/stage5_manifest.json`；人类可读报告：`project_artifacts/formal_study/stage5_real_model_report.md`。
- 阶段 5 结论：真实 provider RSI pilot 已完成；外部正式数据 Gate 仍阻断，且本阶段不是模型权重训练，不产生外部 benchmark 主结论。

### 阶段 5 最终验证（2026-09-28）

- 新增阶段文件的 JSON 解析通过：`stage5_manifest.json`、最新 invocation 的 `summary.json` 和 `analysis.json` 均可读取。
- 最终回归：`py -3.12 -m pytest -q --basetemp=.pytest-stage5-final-verify` 为 `86 passed in 43.62s`。
- `py -3.12 -m compileall -q src project_artifacts/phase3_experiments/scripts tests` 退出码 0；`git diff --check` 退出码 0。
- 这些验证只证明代码和证据文件一致可复核，不改变 `claims_allowed=false` 或外部 formal gate blocked 的结论。

### 阶段 5 Git 收尾（2026-09-28）

- 阶段 5 文档与 manifest 已提交：`94ee97c`（`record real-model RSI pilot`）。
- 已推送到 `origin/codex/closed-loop-rsi`；推送后本地与远程 hash 均为 `94ee97c274bcf637dc485e42e1d8f3a19db2fbc8`。
- 收尾时工作树干净，结果目录仍保留在 `project_artifacts/results/qualification/real-model/`，并未把被忽略的二进制/运行中间文件混入提交。

## 通用 Office WorkAgent 执行器：实现与验收中（2026-09-30）

- 用户确认先搭建通用 Office WorkAgent；首版支持 Excel、Word、PowerPoint 从零创建和基于输入副本编辑，再执行评估与 RSI。
- 设计采用本机 Codex CLI + Ollama `qwen2.5:7b`，模型在每次运行的独立工作区通过 Python Office 库产出真实文件；输入原件只复制、不覆盖，WorkAgent 失败不自动降级模板生成器。
- 已核验 Codex CLI `0.157.1`、Ollama `0.34.4`、`qwen2.5:7b` 可用，Word/Excel/PowerPoint COM 均为 `16.0`；Docker daemon 不可用。`workspace-write` 的工作区外读取限制尚未证实，因此真实运行仅用项目生成的非敏感文件，且不宣称容器级隔离。
- 六项自建 pilot 将覆盖三种格式的创建和编辑；先记录真实 baseline，再用冻结检查器与跨格式回归运行 RSI。它只属于 project-generated 工程证据；不人为制造失败、不改模型权重、不冒称外部 benchmark。
- 规格文档 `docs/superpowers/specs/2026-09-29-general-office-workagent-design.md` 已于 2026-09-30 获用户批准。
- 详细实施计划已写入：`docs/superpowers/plans/2026-09-30-general-office-workagent.md`；用户已批准继续。基线回归为 `86 passed`。当前按计划进行 TDD 实现；Task 1 与 Task 2 已完成，Task 3 正在开发，尚未运行本阶段真实 Office 生成或 RSI。
- 预检补充：RSI 的不完整 baseline/candidate split 必须停止在评分和晋级之前；hidden/OOD 逐任务行不传给候选生成器；WorkAgent 成本以完成任务的实际耗时计算，token 用量未报告时记为 unavailable，不沿用旧占位成本。
- Task 1 已完成并提交：`ce8ea93`（WorkAgent typed config、响应契约和 JSON Schema）；RED 用例确认缺少 `workagent_provider` 时测试收集失败，GREEN 为契约测试 22 passed，全套回归 108 passed；独立任务审阅通过。
- Task 2 代码已提交：`d3c5613`；provider 定向测试 5 passed，契约模块 26 passed，全套回归 112 passed。Codex/Ollama 尚未在本任务内做真实生成调用；任务审阅正在进行。
- Task 2 审阅发现：需在复用运行目录时防止读取上一次遗留的 `agent_response.json`。当前正在用回归测试修复该问题；这期间不将 Task 2 标记为完成。
- Task 2 复审通过：`75ad666` 为每次调用分配唯一 response 文件，复用目录的回归测试通过。WorkAgent 通过 Harness 运行时应为每项任务分配唯一 run 目录；Task 4 将验证该约束。直接复用同一记录目录会覆盖其他过程日志的风险已登记。
- Task 3 正在实施：安全复制 Office 输入、prompt 与输出清单校验；将覆盖来源哈希不变、跨格式拒绝、symlink/path traversal 拒绝和 evaluator constraints 不泄漏。未触发真实模型调用。
- Task 3 已完成并通过独立审阅（提交 `7dd38c7`、绝对路径授权修正 `f38b984`）：显式列出的本机绝对输入路径可读取并复制，UNC、路径遍历、目录、缺失文件、重解析点和跨 Office 域格式仍拒绝；输入原件与副本在 provider 运行后复核哈希；prompt 不含 `expected_constraints`；只接纳响应和 `deliverables.json` 一致的安全输出。全量测试 `131 passed, 3 skipped`；3 项 symlink 用例因当前 Windows 权限不能创建链接而跳过。审阅仅指出一项低风险证据问题：复用 workspace 时，清理旧 canonical response 前计算的 workspace hash 可能包含该旧文件；已登记供最终审阅判断，不影响唯一响应路径的过期响应防护。
- Task 4 已完成并通过独立审阅（`ce4591f` 集成，`3964c2a` 修复）：WorkAgent 默认 Harness 路径下的持久 `task.json` 现在排除 evaluator constraints 与原始输入路径；完整 TaskSpec 仅留在内存供评估/复制使用。进程启动 `OSError` 被记为 `UNAVAILABLE`，保留 provider record 并发出 `provider_output` + 单一终止事件。修复前 RED 为 `2 failed`（分别命中 constraints 泄露与错误终态），GREEN 两项新测 `2 passed`；Office/Harness 子集 `65 passed, 3 skipped`，全量 `139 passed, 3 skipped`。两项审阅问题均由限定复审确认已解决；真实 Codex/Ollama Office 生成尚未运行。
- Task 5 CLI 与资源打包已完成并通过审阅（`aa56014`、路径/临时目录修复 `0f7704d`）：`workagent` provider、YAML 相对输入解析、prompt/schema wheel 内容已验证；外部 `--results-dir`、越界/root-level `--output` 被拒绝，README pytest 临时目录统一至 results。修复测试 `62 passed, 3 skipped`，审阅复核 CLI 定向 `9 passed`；编译和 diff 检查通过。
- Task 6 六项真实 Office qualification 已完成首次单次运行，结果 **0/6 合格**。COM capability probe 三项均为 16.0；本机 Codex CLI 0.157.1 + Ollama `qwen2.5:7b` 共尝试 6 次，5 次响应声称完成但没有 `deliverables.json` 或 Office 文件，Word 编辑任务明确报告没有执行编辑。故无产物可做 Office evaluator 或 COM 重开检查，不能计为成功；三份生成输入源文件哈希运行前后一致。完整证据位于 `project_artifacts/results/qualification/general-office/20260929T190856Z-ab3365c5/`，pilot 报告见同目录 `qualification_report.md`；冻结 evaluator SHA-256 为 `244043c1baf962ae5b20c4caff2dfef5cfbfdb39e1ec57d1477944a9d8b3ed6b`，任务 config SHA-256 为 `ac97763890ef7775f1ed6f004358c594932d7fe4585de0a8a74dc729dd202bca`。输出证据中的 Codex 日志还提示 `qwen2.5:7b` 使用 fallback metadata，可能影响工具执行；当前原因仍待诊断。未重跑任务、未造文件、未使用模板回退。本次结果仅是工程 qualification 失败记录，未开始 RSI，也不支持 Office 创建/编辑已跑通的结论。
- Task 6 实现审阅还发现冻结任务的部分 PowerPoint/Word 版式要求超出现有 evaluator 的检查范围、COM reopen 可能早于 evaluator 成功、单任务异常可能中断后续任务，且 characterization 测试未覆盖所有六个约束；已进入 fix round 1。另依据 provider trace，模型没有发出文件操作工具调用，prompt 将增加明确的执行/验证步骤；不会更换模型或改写首轮失败结果。首轮 0/6 证据保留不变，任何修复后运行都将使用新目录并明确记录重试关系。
- Task 6 fix round 1 已提交 `ce1a820` 并经限定复审通过；冻结 evaluator 未改动，Word/PPT 用户指令收窄为 evaluator 实际检查的范围，COM reopen 仅在 Harness 与 evaluator 均成功后执行，单项异常会写失败记录并继续六项流程，新增六项任务各自的正/负 Office fixture。prompt 已明确要求先用工具写并运行本地 Python、重开验证 Office 文件、写清单，再允许报告 completed。没有重跑模型。修订后 task config SHA-256 `4da03e4870c8843f3597cb420d1c62141d751bc3a477c9f5623a33bb7bd27f39`，原始 `0/6` invocation 与其配置 hash 保持不变；下一次结果必须标为新配置的 retry lineage。qwen2.5:7b 的 fallback-metadata 警告尚未消除。
- 在复跑前追加一项自动留证要求：runner 将支持经过校验的 `--retry-of`，在新 invocation 的 summary/report 中写入首轮 invocation、前后 config hash 和 prompt/criteria 修订原因；避免手工修改或补标结果文件。该 lineage 功能的 TDD 修复正在进行，尚未启动第二轮模型运行。
- Task 6 retry-lineage 修复已提交 `258debb`、`b5037e0` 并经限定复审通过：`--retry-of` 现在验证源 pilot 标识、invocation 路径、64 位小写 SHA-256、任务行/计数一致性；非法摘要会在创建新 invocation 前拒绝，合法预检失败摘要仍可被引用。RED 8 项失败、GREEN 11 项通过；全量 Office 测试 90 passed、3 skipped。主目录未新增测试目录，测试临时文件位于 `project_artifacts/results/test-runs/`。
- 2026-09-30 第二次真实六任务 qualification 已以新配置运行，invocation 为 `project_artifacts/results/qualification/general-office/20260929T195704Z-a4674234/`，通过 `--retry-of` 明确关联首轮 `20260929T190856Z-ab3365c5`。结果仍为 **0/6 合格**：六次 Codex/Ollama 进程均 exit 0、结构化响应均自称 completed，但没有 `deliverables.json` 或合格 Office 输出，Harness 六项均因缺少清单失败；Office evaluator 与 artifact COM reopen 均未运行。三种 COM capability probe 仍为 16.0，所有源输入哈希前后不变。每条 trace 只见模型错误/最终文本事件，没有 shell 或文件操作工具事件；stderr 持续报告 `qwen2.5:7b` 未识别并使用 fallback model metadata。该警告与未调用工具同时出现，但因果尚未证实。此次 invocation 完整记录 prior/new config hash 和修订原因；未做模板回退、未重跑单项、未手工造结果。
- RSI 执行门禁继续关闭：每种 Office 格式尚无创建与编辑成功结果，不能把缺失产物记作分数，也不能启动真实 WorkAgent RSI。下一步需先解决 Codex 本地 provider 的工具调用兼容性，或经授权更换模型/provider 并重新进行独立资格运行；任何替代模型结果都必须作为新配置、新 invocation 明确记录，不能并入当前 Qwen 结果。

### Task 8：通用 WorkAgent RSI 预检（2026-09-30）

- RSI 入口 `project_artifacts/phase3_experiments/scripts/run_workagent_rsi.py` 在模型调用前冻结 12 项 project-generated 任务配置、seed、四组 split hash、三份新生成输入的 SHA-256、实时 evaluator hash、基线 skill hash、Codex/Ollama `qwen2.5:7b` 身份、超时及晋级阈值。
- 六任务 WorkAgent qualification 的首轮 `20260929T190856Z-ab3365c5` 与第二轮 `20260929T195704Z-a4674234` 均为 **0/6 成功**。第二轮六条终态均为 FAILED；没有合格 Office 产物，因而没有 artifact evaluator 成功或 COM 产物重开。三种 Office COM capability 16.0 仅说明环境可用，不代表产物通过。
- 新 invocation `project_artifacts/results/qualification/general-office/20260929T210812Z-e0610074/` 保存 `contract.json`、`summary.json`、`analysis.json` 与中文 `qualification_report.md`；状态为 blocked、`rsi_started=false`、`candidate_started=false`。未重跑 qualification、未调用模型、未切换到 Mistral、未将失败/不可用转换为分数。
- 此阻断结论不影响历史 B0/local executor 与 E05 fixture 的独立证据，也不将它们当成通用 WorkAgent 成功或外部 benchmark 成绩。后续仍须先解决本地 provider 文件操作兼容性并重新做独立六任务资格运行；外部正式数据 gate 依旧关闭。

#### Task 8 fix round 1

- 预检修复：缺失/损坏 baseline summary 时仍会保存 blocked `summary.json`、`analysis.json` 与中文报告；合格基线若 RSI runner 抛异常，会保留局部证据并保存 failed 报告；incomplete/failed 不再返回成功退出码。`--baseline-invocation` 仅接收结果根目录下的直接子目录 ID。
- 最终新 invocation `project_artifacts/results/qualification/general-office/20260929T212754Z-45c2bcc1/` 仍为 blocked，未调用模型/候选 provider。最新六任务资格运行仍为 **0/6 成功、6 failed、0 unavailable**；首轮同样为 **0/6 成功、6 failed、0 unavailable**。前一预检 invocation `20260929T212106Z-98ecd0ee` 亦保留，不混同基线。
- `source_office_validation.json` 留存本次新生成的三份 **输入** 文件各自的库重开、SHA-256 不变和 COM 16.0 重开证据；它不是 WorkAgent 输出产物验证，不能替代缺失的创建/编辑资格证据。

#### Task 8 fix round 2

- 候选 provider 在调用子进程前会保存 `candidate_launch_attempt.json`，因此即使子进程启动报错、provider 记录尚未写出，汇总仍能准确显示候选启动尝试；新增 PermissionError 回归测试验证此路径。真实预检仍在资格门禁处阻断，`candidate_started=false`。
- Task 8 全量测试 `200 passed, 3 skipped`；`compileall` 和 `git diff --check` 通过。没有调用真实 WorkAgent/candidate provider，也没有更换模型。实际 RSI round 仍因 0/6 基线资格失败而未运行。

#### Task 6 fix round 2：通用 Office 六项资格通过（2026-09-30）

- 修复了本地 Ollama Office 控制提示：模型必须把用户任务转成逐项清单，在脚本中对每个要求的工作表、单元格、公式或文档/幻灯片结构做精确断言；断言失败必须修复并重新验证后才可写清单。新增回归测试先失败后通过，目标 Office 测试为 `108 passed, 3 skipped`。
- 独立 Excel 重跑 `20260930T180717Z-dba8d4ad` 已通过：Harness `SUCCEEDED`、evaluator score `1.0`、Excel COM `16.0` 重开成功。
- 六项真实 qualification invocation `20260930T180920Z-687c4ab7` 已通过：`6/6 succeeded`、`0 failed`；Excel create/edit、Word create/edit、PowerPoint create/edit 均为 evaluator `True`、COM `True`、input hashes `True`，每项均有非空 artifact SHA-256。该证据是 project-generated engineering pilot，不是外部 benchmark。
- 六项输出与逐项证据保存在 `project_artifacts/results/qualification/general-office/20260930T180920Z-687c4ab7/`。RSI 尚未启动，下一步只运行 preflight 验证基线身份与哈希。

#### Task 6 fix round 3：PowerPoint 编辑工具面修正与定向复验（2026-10-01）

- 复核上次 PowerPoint 编辑超时 `20260930T202627Z-72805dbe`：模型已写脚本并生成 PPTX，但连续用 `read_file` 读取二进制文件；工具拒绝后模型未转用 `python-pptx`，最终 240 秒超时。输入 PPTX 前后 SHA-256 一致；此运行不计成功。
- 工具协议修正：Office 任务不再向 Ollama 暴露文本 `read_file` 工具，提示明确要求使用匹配的 Python Office 库；非 Office 文本任务仍保留该工具。测试先 RED（当前工具清单仍暴露 `read_file`），修正后定向验证 `3 passed`。
- 独立真实 PowerPoint 编辑 invocation `20260930T203703Z-444f4890` 通过：Harness `SUCCEEDED`，evaluator `passed=true`，PowerPoint COM `16.0` 重开成功，输入哈希前后相同，artifact SHA-256 为 `6ce12a97a6be69d968661fd7f79134532f1bef16aee49ee4e7a82986aa5fb4c6`。这是单项定向成功，不能替代当前配置下的新六项资格矩阵。
- Office 测试文件回归为 `114 passed, 3 skipped, 1 failed`；唯一失败是既存 PowerPoint 提示措辞断言与当前等价文案不一致（测试期待 `save the phrase on an existing slide`，提示现为 `choose exactly one existing slide, save it there`）。全量资格和 RSI preflight 尚未运行；RSI 仍未启动。
- 后续 `excel-edit` 定向 invocation `20260930T203952Z-2b52910a` 通过：Harness/evaluator/Excel COM `16.0` 全部通过，输入哈希未变化。更新陈旧的 PowerPoint 提示测试措辞断言后，待复跑模块测试确认。

#### Task 6 fix round 4：Excel 创建清单与 PowerPoint 创建版式（2026-10-01，进行中）

- 六项 retry `20260930T204228Z-31ab3b3d` 的汇总为 **4/6**。Excel 编辑、Word 创建/编辑、PowerPoint 编辑通过 evaluator、COM 16.0 和输入哈希门槛；Excel 创建在 240 秒超时（模型把 manifest 对象传给只接受字符串的 `write_file`，之后又传了非 JSON 路径文本）；PowerPoint 创建缺少必需形状文本并检测到 6 处重叠。原始 invocation 与产物未修改。
- 根因对应修正：明确 manifest 工具参数必须是含 JSON 文本的字符串；PowerPoint 创建使用空白版式、按指定幻灯片分配文本，避免默认占位符与文本框重叠。新增提示回归测试先 RED `2 failed` 后 GREEN `2 passed`；WorkAgent Office 模块测试 `116 passed, 3 skipped`。
- 新六项 retry invocation `20260930T205542Z-ddfe237f` 已启动，并通过 `--retry-of 20260930T204228Z-31ab3b3d` 记录 lineage；尚无最终汇总。RSI 仍未启动，需等该轮六项证据检查完成。

#### Task 6 fix round 5：Excel 提示修正与新一轮六项资格（2026-10-01）

- 检查发现 fix round 4 的六项 invocation `20260930T215835Z-f6a3f412` 为 **4/6**：Excel 创建因缺少 `deliverables.json` 失败；PowerPoint 创建虽产出文件，但 evaluator 检出幻灯片数为 1（预期 3）。其余 Excel 编辑、Word 创建/编辑、PowerPoint 编辑均通过 evaluator、COM 16.0 重开和输入哈希检查。
- 结合 provider trace 调整 Excel 提示：区分新建与重开已有工作簿，要求公式写入 `.value`，并按任务给定字面值逐格赋值，不从行号或循环推导数据。PowerPoint 提示要求对每个指定页面分别调用 `add_slide` 并把内容放入对应页。未降低 evaluator、未改历史 invocation。
- 提示回归断言先 RED，修改后通过；本轮 fresh 定向回归 `157 passed, 3 skipped, 1 deselected`（`tests/test_workagent_office.py`、`tests/test_office_capabilities.py`、`tests/test_workagent_final_review.py`，pytest 临时文件在 `project_artifacts/results/test-runs/20261001-office-gate-preflight/`）。此前最新 Office 模块测试为 `121 passed, 3 skipped`，门禁回归为 `23 passed`。
- 独立 Excel 创建 invocation `20260930T221401Z-7616435e` 通过：Harness `SUCCEEDED`、evaluator `passed=true`/score `1.0`、Excel COM `16.0` 重开成功、输入哈希检查通过；产物 SHA-256 `7c828bab9738ebd95248d58f83a64fb67cbbb7e11abdf33895319a9520f03afb`。此单项结果不替代六项资格。
- 本轮资格总矩阵尚未重跑，RSI 仍未启动。下一步创建全新六项 invocation，并以 `--retry-of 20260930T215835Z-f6a3f412` 记录重试关系；逐项核对 Harness、evaluator、COM、输入哈希和产物 SHA-256。只有六项全部合格才运行 RSI preflight。
- 新六项 invocation `20260930T221840Z-5c9c4ee1` 已完成，并通过 `--retry-of 20260930T215835Z-f6a3f412` 记录 lineage；结果 **3/6 succeeded、3 failed、0 unavailable**。Excel 编辑、Word 创建/编辑通过 evaluator、各自 Office COM 16.0 重开和输入哈希检查；其余三项失败且未进入 evaluator/COM 产物重开。三个源输入的源文件哈希检查均为 true。provider 均自报 completed/exit 0，但这不等同于产物完成。
- Excel 创建 trace 显示模型生成脚本对 openpyxl 的单元格范围赋值有误，连续修正后仍未写 `deliverables.json`，Harness 因缺少清单失败；未生成合格 artifact。PowerPoint 创建 trace 声称已完成并提前写入清单，但实际运行的 Python 脚本语法失败，目标 PPTX 不存在。PowerPoint 编辑则多次生成无效的 `deliverables.json`/脚本内容，最终声称 completed，但 `outputs/updated_briefing.pptx` 不存在。没有模板回退或手工补产物。
- 本轮逐项证据在 `project_artifacts/results/qualification/general-office/20260930T221840Z-5c9c4ee1/`；summary 显示 `success_count=3`、`failure_count=3`，COM capability 均为 16.0，失败项 artifact hash 为空，且报告明确三项均未通过 Harness。全矩阵资格门禁仍关闭；按门禁条件不运行 RSI preflight，也不启动 RSI/candidate。
- 当前失败已收敛到小模型在 Excel/PPT 任务中的代码生成、工具错误后的修复以及过早报告完成；可审计 trace 已保存。后续需针对这些工具反馈/任务完成契约继续修复或确认兼容 provider，再使用新 invocation 复跑；不应仅重复相同配置并把失败解释成 Office COM 环境问题。

#### Task 6 fix round 6：扩大工具预算与编辑指令明确化（2026-10-01）

- 根据上一轮 `20260930T223531Z-59a31f3c` 的逐项失败证据，资格 runner 的 `max_tool_turns` 从 40 增至 48；Word 编辑指令要求重组为指定标题结构而非只追加内容；PowerPoint 编辑任务按输入模板已核实的 10 x 7.5 英寸页面布局，将新增文本框固定到 slide 1 的 `left=1.0, top=2.25, width=8.0, height=1.0` 英寸，并要求断言不与已有形状重叠。新增/既有回归测试先 RED、后 GREEN。
- Office 模块测试 `124 passed, 3 skipped`；完整测试 `258 passed, 3 skipped`；`compileall` 通过；`git diff --check` 通过（仅有工作树既有 LF/CRLF 提醒）。全量测试首次因两个并发 pytest 共用同一 `--basetemp` 引发 SQLite 文件占用，串行改用独立目录后完整通过。
- 新 qualification invocation `20260930T225838Z-1b6bae56` 通过 `--retry-of 20260930T223531Z-59a31f3c` 记录 lineage，结果仍为 **3/6**。Excel 创建、Excel 编辑、Word 创建通过 Harness、evaluator、COM 16.0 重开和源哈希检查；Word 编辑与 PowerPoint 创建缺少安全的 `deliverables.json`，PowerPoint 编辑返回不符合 schema 的未完成 `writing_manifest` 状态。失败项没有进入 evaluator/COM 产物检查；源输入哈希保持不变。没有模板回退或手工补产物。
- 完整结果与 provider/tool trace 保存在 `project_artifacts/results/qualification/general-office/20260930T225838Z-1b6bae56/`。六项门禁仍关闭，不运行 RSI preflight 或候选 provider；下一步依据各任务 `provider_records/tool_events.jsonl`、`provider.stdout.jsonl` 与 agent workspace 确认模型停滞/manifest 缺失的具体调用链，再针对根因做新的定向回归和资格运行。

#### Task 6 fix round 7：provider manifest 收尾与 Office 提示修复（2026-10-01）

- 新增 provider 回归覆盖真实失败形态：Office 文件已经存在，模型却返回 schema 非法的 `writing_manifest` 状态。测试先 RED，证实原通用纠正会要求“不要调用工具”；修正后 provider 明确要求以字符串参数调用 `write_file` 写根目录 `deliverables.json`。Office 模块测试 `126 passed, 3 skipped`，完整测试 `260 passed, 3 skipped`；`compileall`、`git diff --check` 通过。
- 新六项 qualification `20260930T231323Z-ec00a301` 以 `20260930T225838Z-1b6bae56` 为 retry lineage，结果 **2/6**。Excel 创建/编辑均通过 Harness、冻结 evaluator、Excel COM 16.0 重开与输入哈希门槛。Word 创建/编辑产出了 DOCX，但 evaluator 拒绝：创建任务三个要求的 Heading 1 中两个被错误设为 Heading 2；编辑任务要求的 Heading 1/2 未按段落结构保留。Word 编辑脚本曾报 python-docx Paragraph API 错误，provider 修正并重跑脚本，但最终内容仍未通过 evaluator。
- PowerPoint 创建在 240 秒 provider timeout，trace 显示模型生成含字面换行的非法 Python 字符串，工具反馈 SyntaxError 后没有继续修复；PowerPoint 编辑因重叠检查把新文本框自身也当成既有形状，连续断言失败，最终缺少安全 manifest。六项源输入哈希均保持不变；失败项未进入 evaluator/COM 成功验收。完整逐项 trace 位于该 invocation 各任务的 `provider_records/` 与 `result.json`。
- 不伪造或补写产物，RSI preflight/实验及 candidate provider 均未启动。下一轮针对 Word 标题层级与段落 API、PowerPoint 换行转义和“添加前快照既有形状”的明确指令添加回归后，再以全新 invocation 重跑六项。

#### Task 8：真实 Office RSI 一轮闭环完成（2026-10-01）

- 以已通过的六项资格 invocation `20261001T053355Z-f2d4995e` 为 immutable baseline，执行命令为：`py -3.12 project_artifacts/phase3_experiments/scripts/run_workagent_rsi.py --baseline-invocation 20261001T053355Z-f2d4995e`。本次使用本地 Ollama `qwen2.5:7b`，未切换模型、未改写历史结果。
- 新 invocation 为 `project_artifacts/results/qualification/general-office/20261001T065932Z-9faf97ae/`，顶层状态 `completed`，`rsi_started=true`、`candidate_started=true`。四个 split 均完整执行，没有把 timeout/unavailable 转成分数。
- baseline 分数：develop `2/3`（`0.6667`，PowerPoint create 的页数为 4 而预期 3）；regression `2/3`（`0.6667`）；hidden `3/3`；OOD transfer `3/3`。
- Ollama 候选 provider 实际返回结构化候选并通过 path、leakage、patch-schema、compile 验证。候选 develop 为 `3/3`（`1.0`），regression 仍 `2/3`，hidden/OOD 均保持 `3/3`；成本增量约 `0.0974`，无 critical regression，所有 promotion gates 为 true。
- 候选 `1.0.1` 被接受并注册为 `office.workagent` champion `1.1.0`，证据引用为 `f1ebc061c752a804ad27822bcf26aa875db74579366bf6562b047e328cc99a38`；checkpoint、candidate provider record、逐任务 baseline/candidate 结果均保留在 invocation 目录中。
- 这是一轮 project-generated engineering RSI pilot：不能表述为四 split 全部通过、12/12 全通过、模型权重训练或 external benchmark。外部正式数据的许可证/来源门禁仍保持阻断；下一步应在新增任务与更稳健候选诊断后继续实验，而不是覆盖本次证据。

#### 最终回归验证（2026-10-01）

- 使用 `py -3.12 -m pytest -q -p no:cacheprovider --basetemp=project_artifacts/results/test-runs/final-20261001 tests`，结果为 `267 passed, 3 skipped`。
- `py -3.12 -m compileall -q src project_artifacts/phase3_experiments/scripts tests` 退出码为 `0`；`git diff --check` 无内容错误（仅报告 Windows LF/CRLF 转换提示）。
- 本次验证没有修改任何历史 qualification/RSI 结果；所有临时测试文件仍位于 `project_artifacts/results/test-runs/`。
- 清理候选 provider 的重复导入并将实施计划勾选为完成后，使用独立目录 `project_artifacts/results/test-runs/final-20261001-r2/` 再次运行完整测试，结果仍为 `267 passed, 3 skipped`；compileall 仍为 `0`。
