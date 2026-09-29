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

## 通用 Office WorkAgent 执行器：规格待审（2026-09-29）

- 用户确认先搭建通用 Office WorkAgent；首版支持 Excel、Word、PowerPoint 从零创建和基于输入副本编辑，再执行评估与 RSI。
- 设计采用本机 Codex CLI + Ollama `qwen2.5:7b`，模型在每次运行的独立工作区通过 Python Office 库产出真实文件；输入原件只复制、不覆盖，WorkAgent 失败不自动降级模板生成器。
- 已核验 Codex CLI `0.157.1`、Ollama `0.34.4`、`qwen2.5:7b` 可用，Word/Excel/PowerPoint COM 均为 `16.0`；Docker daemon 不可用，首版安全边界明确为 Codex `workspace-write`，不宣称容器级隔离。
- 六项自建 pilot 将覆盖三种格式的创建和编辑；先记录真实 baseline，再用冻结检查器与跨格式回归运行 RSI。它只属于 project-generated 工程证据；不人为制造失败、不改模型权重、不冒称外部 benchmark。
- 规格文档已写入：`docs/superpowers/specs/2026-09-29-general-office-workagent-design.md`。当前等待用户审阅规格；在其批准前，尚未改动 WorkAgent 生产代码，也未运行本阶段的真实 Office 生成任务。

### Task 8：通用 WorkAgent RSI 预检（2026-09-30）

- RSI 入口 `project_artifacts/phase3_experiments/scripts/run_workagent_rsi.py` 在模型调用前冻结 12 项 project-generated 任务配置、seed、四组 split hash、三份新生成输入的 SHA-256、实时 evaluator hash、基线 skill hash、Codex/Ollama `qwen2.5:7b` 身份、超时及晋级阈值。
- 六任务 WorkAgent qualification 的首轮 `20260929T190856Z-ab3365c5` 与第二轮 `20260929T195704Z-a4674234` 均为 **0/6 成功**。第二轮六条终态均为 FAILED；没有合格 Office 产物，因而没有 artifact evaluator 成功或 COM 产物重开。三种 Office COM capability 16.0 仅说明环境可用，不代表产物通过。
- 新 invocation `project_artifacts/results/qualification/general-office/20260929T210812Z-e0610074/` 保存 `contract.json`、`summary.json`、`analysis.json` 与中文 `qualification_report.md`；状态为 blocked、`rsi_started=false`、`candidate_started=false`。未重跑 qualification、未调用模型、未切换到 Mistral、未将失败/不可用转换为分数。
- 此阻断结论不影响历史 B0/local executor 与 E05 fixture 的独立证据，也不将它们当成通用 WorkAgent 成功或外部 benchmark 成绩。后续仍须先解决本地 provider 文件操作兼容性并重新做独立六任务资格运行；外部正式数据 gate 依旧关闭。

#### Task 8 fix round 1

- 预检修复：缺失/损坏 baseline summary 时仍会保存 blocked `summary.json`、`analysis.json` 与中文报告；合格基线若 RSI runner 抛异常，会保留局部证据并保存 failed 报告；incomplete/failed 不再返回成功退出码。`--baseline-invocation` 仅接收结果根目录下的直接子目录 ID。
- 最终新 invocation `project_artifacts/results/qualification/general-office/20260929T212754Z-45c2bcc1/` 仍为 blocked，未调用模型/候选 provider。最新六任务资格运行仍为 **0/6 成功、6 failed、0 unavailable**；首轮同样为 **0/6 成功、6 failed、0 unavailable**。前一预检 invocation `20260929T212106Z-98ecd0ee` 亦保留，不混同基线。
- `source_office_validation.json` 留存本次新生成的三份 **输入** 文件各自的库重开、SHA-256 不变和 COM 16.0 重开证据；它不是 WorkAgent 输出产物验证，不能替代缺失的创建/编辑资格证据。
