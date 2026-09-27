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

- 分支 `codex/closed-loop-rsi` 已推送到 `origin`；远程和本地提交均为 `95ad2eabeba35de73406ef6cc38942d37491dfef`。

## 下一步

1. 提交阶段 4 metadata-only 门禁、正式矩阵、guarded runner 和分析器，并记录完整测试证据。
2. 继续核验 SpreadsheetBench workbook 级来源和许可；在 `verified + checksum + quality + leakage` 全部满足前，保持 formal runner 拒绝。
3. 只有外部数据 Gate 通过后，才下载官方 archive、生成 raw/interim/processed 层并运行 formal matrix；否则继续进行不带外部 benchmark 声明的 pilot/工程验证。
