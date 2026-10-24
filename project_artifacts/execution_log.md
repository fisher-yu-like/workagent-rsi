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

### Hardening T00 local baseline (2026-10-17)

- Isolated branch `feat/evaluation-rsi-hardening` starts at `main@43f89d54daed37aba9f0e79a7df79b3288b2f993`; the user's original worktree and untracked notes were not changed.
- Explicit interpreter: `D:\ws\Projects\WorkAgent-RSI\.venv\Scripts\python.exe`, Python 3.13.6. Raw full suite: 149 passed, 4 failed, exit 1. Exact command, cwd, dependency versions, timestamps, stdout/stderr and hashes are in `project_artifacts/results/hardening-v2/T00/20261017T224647995/baseline/`.
- T00 environment manifest records Git/installed dependencies/tool presence; API connectivity and Office COM were deliberately not probed. The manifest is not evidence of a successful model or COM run.
- Environment-manifest tests: 2 passed. An initial in-memory Python runner failed before pytest due PowerShell quoting; the failed attempt is recorded in the local progress log. A first implementation of Git status parsing lost a leading space and was corrected after a focused test failed.
- External formal data work is marked blocked because source/license evidence remains incomplete; no external dataset was downloaded.

### Hardening T02 local failure explanation (2026-10-17)

- On main@43f89d5, raw local full suite: 149 passed, 4 failed. Three failures shared a CandidateVerifier command using unavailable `py -3.12` (compilation exit 103); the fourth was a Word fixture that copied `REQUIRED-001` into the title and incorrectly gave the bad baseline full credit.
- New independent command/artifact assertions first failed 2/2 for those exact causes; raw stdout/stderr and invocation are retained under `project_artifacts/results/hardening-v2/T02/20261017-red/`.
- CandidateVerifier now uses `sys.executable` for compile and pytest. The Word fixture excludes the expected token from its instruction; closed-loop tests assert baseline 0, repaired candidate 1, promotion, and rollback content hash.
- Focused tests: 18 passed. Full local suite: 157 passed in 113.60s, exit 0; raw invocation and output under `project_artifacts/results/hardening-v2/T02/20261017-full/`. Details in `project_artifacts/formal_study/hardening_t02_failure_explanation.md`.
- T01's independent R01-R12 review corpus is pending. No live API/model, Office COM, rendering, or external formal data was validated in this stage.

### Hardening handoff and T01 (2026-10-21)

- Continued existing `feat/evaluation-rsi-hardening@5c727a3`; original `WorkAgent-RSI` checkout, branch and untracked user notes preserved.
- Fresh unchanged engineering baseline: 157 passed, exit0. Evidence: `results/hardening-v2/handoff-legacy-baseline/20261021T074934481123Z/`. Two earlier runner/environment attempts are retained separately: long-path WinError206 and missing basetemp parent WinError3; neither is T01 functional evidence.
- T01: 12 independent active red tests, one passing exact-formula control, one passing case-manifest integrity check; 12 failed / 2 passed / 0 errors, exit1. Evidence: `results/hardening-v2/T01/20261021T074951807941Z/`; fixture observations and Office files are preserved in generated.zip.
- Each R01–R12 has a source-independent truth, minimal input, desired behavior, actual observation and owner task. No xfail, skip or collection suppression was added. These defects remain open.
- Canonical copy of the supplied plan and a common task ledger are now in this worktree. T03 is the only primary task in_progress.
- No live model calls or external data. R12 runs only authored probe code against its own temporary parent sentinel, with a sanitized environment and a dummy value; it does not read real credentials or protected data.

### Hardening T03 and final handoff validation (2026-10-21)

- Added strict, versioned ExecutionOutcome/AssessmentOutcome/RunUsage/ProtocolCapabilities and explicit legacy adapters. Unknown counts/costs remain null, observed zero requires available telemetry, and ambiguous old failure causes remain null. Old report fields and pipeline decisions are unchanged.
- Added exclusive evidence bundles with relative paths, SHA-256 and size validation, metadata credential rejection and separately recorded executor/candidate/judge capabilities. Arbitrary evidence file bodies must already be sanitized by the caller.
- T03 interface red: two expected missing-module collection errors in `results/hardening-v2/T03-red/20261021T075209002525Z/`. Final focused checks: 17 passed in `results/hardening-v2/T03/20261021T075640278743Z/`.
- Refined R10 to preserve max_attempts as execution retries; the future repair loop must use explicit repair_policy. Latest T01: 12 failed / 2 passed / 0 errors in `results/hardening-v2/T01-final/20261021T075943272086Z/`.
- Final full suite: 176 passed / 12 failed / 0 errors / 0 skips, exit1, in `results/hardening-v2/handoff-final-verified/20261021T080224738698Z/`. Exactly the twelve expected-open R01–R12 cases fail. All tested source hashes were rechecked after the run.
- Actual schema export, evidence bundle and successful relocation/integrity check: `results/hardening-v2/T03/20261021T080824087553Z/contracts/`. The bundle includes raw logs, source hashes, independent observations, owner map and generated fixtures.
- T00/T01/T02/T03 are completed as scoped; later repairs are pending. The original worktree, branch, user notes and historical run evidence are preserved. No live model, external benchmark or three-domain rendering qualification was run.
- Local commits only; no push, PR, merge or deployment.

## 2026-10-23 ? T03 section 2.7 completion

Current work directory is `D:/ws/Projects/WorkAgent-RSI`, existing branch `feat/evaluation-rsi-hardening`. Added strict `LiveCallPolicy` and default-off JSON configuration: explicit approval, matching provider/model/endpoint, finite call/tool/time caps, optional observed-cost cap, timezone-aware approval source, and credential-free endpoints. It is an additive approval contract; T22/T31 runtime counters and orchestration are still pending. Red: missing interface, 1 collection error (not a behavioral defect); green: 33 passed / 0 failed. Evidence: `project_artifacts/results/hardening-v2/T03-policy-red/20261023T125005764891Z` and `project_artifacts/results/hardening-v2/T03-policy/20261023T125043946935Z`. No live model calls.

## 2026-10-23 — T04 execution boundary

Implemented immutable-image Docker execution and an explicit Apptainer SSH backend for the user's existing `cluster_vlab_jump`. Native API/Ollama run_python now routes only through these interfaces; unavailable isolation never falls back to host Python. CLI-owned sandbox capability remains separate.

The existing Apptainer 1.4.5 module works with the user's existing D-Bus socket and systemd user services. No administrator settings were changed. Initial SIF mounting lacked squashfuse, so a tiny existing BusyBox seed and selected Python/core libraries from an existing SIF were extracted into a private runtime; no application/cache/source content was copied. Nine hash-verified official wheels totaled 14,168,107 bytes, extracted only into that runtime. Provision failures (unsupported unsquashfs flag and missing librt) and all failed preflights are retained, not reported as qualified evidence. Final server-added storage is 199,672 KiB (~195 MiB), including retained failed attempts; no new image download or model call occurred.

Real checks: all 13 boundary assertions passed, with host-side pre-execution cgroup observations of 2 GiB memory, zero swap, 2 CPUs and 128 PIDs. Real XLSX/DOCX/PPTX files were generated remotely, exported and independently reopened locally. A detached-session child timed out; the owned service was absent and its cgroup empty/removed. No owned services remained at final server inspection. Docker daemon access on the cluster is denied and the local CLI is absent; Docker real qualification remains not_run.

Validation: 78 focused passed; final full suite 233 passed / 11 expected-open R01-R11 failures / 0 errors / 0 skipped, pytest exit 1 preserved. R12 now passes. Python source hashes match the final tests and qualified probe. Compileall and diff checks pass. Evidence: `project_artifacts/results/hardening-v2/T04/20261023T131835002830Z/sandbox`, `project_artifacts/results/hardening-v2/T04-verified/20261023T132132594651Z`, `project_artifacts/results/hardening-v2/T04-current-tests/20261023T132034498773Z`. Portable bundle `project_artifacts/results/hardening-v2/T04-handoff/20261023T132138583259Z/bundle/manifest.json` has 29 files and verifies after relocation.

T04 completed within its backend-specific scope. G1 as a whole, T05 input/Office-worker isolation, and T06-T35 remain unfinished. No model performance, visual/COM, research or benchmark claim. Runtime /tmp storage is temporary; missing or changed identity blocks execution. Per-file/transfer bounds do not replace an aggregate disk quota.


### Hardening T05 evaluation and Office-worker isolation (2026-10-24)

Continued on `feat/evaluation-rsi-hardening` at `d1a4697` in the current checkout. T05 only. The independent initial red cases failed 9/9 for behavioral boundary gaps (not missing dependencies). Execution views now contain only declared task inputs; candidate exports reject source links/junctions/hardlinks before resolution, protected history paths and policy/context collisions. Copies are rehashed before/after processing. The renderer has no host Office or Poppler fallback, and unconfigured COM probing/reopening does not activate user applications.

Prepared a private LibreOffice UNO/Poppler runtime inside the existing Apptainer/systemd boundary. Retained 246 Debian archives verified against signed apt metadata (186,961,340 download bytes); package extraction ran no maintainer scripts or host package installation. First actual render exposed missing Debian conffiles; shipped `.registry/*.xcd` bytes were materialized only in the private tree. A second startup exposed first-profile exit 81; the worker now reaps its owned child and permits one bounded restart. Failed attempts remain as evidence. Final runtime identity is `481af80d507540f293116f57b3331c75d5a69f55fa957c3643322fe471360cf7`. The previous T04 runtime identity remains unchanged. Server forwarding was unavailable at resume and restored by the user before actual execution.

Real XLSX, DOCX and PPTX fixtures each rendered to PDF and PNG in the isolated worker. Source/copy hashes stayed unchanged. UNO used ReadOnly=True, MacroExecutionMode=0 and UpdateDocMode=0; the worker uses a unique pipe/profile, an aborting interaction handler and no network. Versions, binary hashes and font/system fingerprints are recorded. The authored remote boundary probe saw only its script and declared input, could not write inputs, could not see local hidden/remote host sentinels and did not inherit the dummy credential variable. During real rendering, a separate owned Office sentinel retained its PID/start time; it was then cleaned by its own creator. A detached Office launcher timed out; its owned unit and cgroup were confirmed absent. Final inspection of the six known probe units found all absent. No user Office process was terminated.

Validation: 38 focused passed; final full suite 250 passed / 11 expected-open R01-R11 failures / 0 errors / 0 skipped, exit 1 retained. All source hashes match the final full tests; 17 new isolation cases account for the increase from T04. Compileall, documented probe --help and diff checks pass. One resumed test command used an absent historical filename (exit 4, no cases); its failed invocation was retained and corrected using discovered test files. The fixture PNGs were visually inspected and readable. This is infrastructure qualification, not general visual/formula acceptance or a model/RSI benchmark. Dedicated Microsoft Office COM remains unavailable. Only seven font files are provisioned. G1 and T06-T35 remain unfinished.

Evidence: `project_artifacts/results/hardening-v2/T05/20261024T041832387079Z` and `project_artifacts/results/hardening-v2/T05-final-full/20261024T041854561992Z`. Summary: `project_artifacts/formal_study/hardening_t05_evaluation_boundary.json`; operations: `deploy/office-worker/README.md`. T04 plus retained T05 preparation consumes 1,301,760 KiB (1.241 GiB), below the user's 4 GB budget; /tmp lifetime and lack of aggregate disk quota remain explicit. The portable handoff bundle location is recorded in the summary and ledger. Local commit only; no push, PR, merge or live model call.


### Hardening T06 candidate context (2026-10-24)

Shared CandidateContext now carries actual champion package and canonical/byte hashes, current develop facts, logical requirement refs, minimal traces, provenance-backed abstract public history and edit/context budgets. API and CLI share the same prompt; compatibility wrappers require an exported skill.json. Loop exports are checked against registry content hashes. Protected promotion refs remain private. Completed develop history is rehashed before resume; no raw hidden rejection is converted into a lesson. Overflow is explicit and never truncated.

Independent red: 9 failed / 0 errors. Final focused: 36 passed. Full: {'passed': 265, 'failed': 10, 'error': 0, 'skipped': 0}; exit 1 preserved. R07 is green; ten future-task regressions remain open. First green had a history fixture with an inconsistent issue-group index; corrected the authored index and reran. All Python and captured test sources match final full evidence. No server/model/API call: API/CLI transports injected offline; multi-round authored policy only. Evidence project_artifacts/results/hardening-v2/T06/20261024T051729272060Z. Scope T06 only; T07 response normalization remains unchanged.


### Hardening T07 candidate normalization (2026-10-24)

T06 implementation committed locally as 8bb3e04f0760362ba2f1b94143ef95faf043034b. T07 now admits the complete raw edit list and metadata before constructing normalized edits. API and CLI use the same registered envelope conversion. Over-budget/forbidden/duplicate/wrong-type edits reject the entire response. Duplicate JSON keys are rejected in raw responses and patch strings. Exact instruction values remain unchanged. Missing model hypotheses/metrics reject; deterministic context/transport metadata supplements have explicit provenance. Actual transport identity owns the normalized provider/model fields; model self-report remains raw evidence. Fresh response roots prevent stale CLI output reuse. Original response text, parsed claims and accepted/rejected normalization records remain available.

T07 independent red: 27 failed / 0 errors. First green 49 passed; final focused 71 passed. Full: {'passed': 295, 'failed': 9, 'error': 0, 'skipped': 0}; exit 1 retained. R08 is green; R01-R06/R09-R11 remain open. Final Python and captured source/test hashes match. Compileall and diff checks pass. Evidence project_artifacts/results/hardening-v2/T07/20261024T052934976672Z includes 16 actual audited offline response examples. No server, live model, push or benchmark run. T08 and T09 remain pending; G1 is not complete.


### T08 local candidate validation; real behavior deferred (2026-10-24)

Centralized complete patch/schema/parent/budget/type checks in CandidateVerifier; RSI and Check share it. JSON skill compilation is not_applicable; candidate-authored tests never run on host. Required rules and explicit task branches are checked as static heuristics. Reports separate schema/safety/behavior/quality; WorkAgent requires real behavior by default and remains not_run/quality unverified without it. Fixed sandbox-probe adapter binds independent program/taskset/package hashes, exact coverage and actual runtime/resource/cleanup traces; unit fixtures cannot qualify real quality. Probe/policy identity is checkpointed.

Red17 failed/0 errors; final focused57 passed. Verified full {'passed': 318, 'failed': 8, 'error': 0, 'skipped': 0} (exit1 preserved); R06 green. A legacy JSON-error message expectation was corrected without hiding defects. One earlier full had a transient Windows checkpoint os.replace PermissionError; its evidence is retained and serial full rerun passed all other than the eight known open cases. Evidence project_artifacts/results/hardening-v2/T08/20261024T055823362222Z. T08 remains partial: real isolated behavior tasks/runtime acceptance deferred by explicit user request. No server/model calls.


### Hardening T09 comparable result cohorts (2026-10-24)

T08 local implementation committed as 7b839c8773f521c9f41a55fd966f04d7446dc271. T08 remains partial: genuine isolated behavior is deferred by user. T09 partitions all eight comparable identities, verifies hash-bound task observations and admission evidence, excludes missing identities/nonfinite metrics/duplicate evidence, selects the latest declared attempt without fallback, and records denominators/source refs. Mixed pilot/formal roots cannot inherit a global mean or claim. New exclusive paired reference runs save per-task comparisons and preserve original history.

Independent red24 failed/0 errors; focused39 passed (33 new cohort cases). Final full352 passed/7 failed/0 errors/0 skipped, exit1 retained, exactly R01-R05/R10/R11. R09 now passes; final source hashes match. The old formal-runner fixture expected aggregation without identity; its assertion now requires explicit exclusion. Actual local CLI and authored paired evaluation produced two separate pilot/formal means, no mixed mean/claim, one selected retry sample and two paired tasks with unchanged historical SHA-256. Compileall, CLI help and diff checks pass. Evidence project_artifacts/results/hardening-v2/T09/20261024T060809298886Z.

Qualification is local protocol engineering only, not a real external benchmark/model evaluation. V1 accepts task-mean metrics; missing legacy identities are not invented. No server, model/API call, push, PR or merge. T09 completed; T10 not started; G1 remains incomplete.


### Hardening T10 local completion (2026-10-24)

{"schema_version": "hardening-t10-v1", "status": "completed", "base_commit": "5c9253ad4cc5920f42ec9d08286ce0546ca77c79", "implementation_commit": "commit containing manifest; exact tested sources hashed in evidence", "completed_at": "2026-10-24T06:39:06.523995+00:00", "scope": "offline authored engineering cases; no server/model/API/external benchmark", "red": {"passed": 0, "failed": 17, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T10-red/20261024T062906891784Z"}, "focused": {"passed": 49, "failed": 0, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T10-final-focused/20261024T063804448372Z"}, "new_tests": 23, "tested_source_hashes_match": true, "evidence": "project_artifacts/results/hardening-v2/T10/20261024T063905253104Z", "bundle": "project_artifacts/results/hardening-v2/T10/20261024T063905253104Z/bundle/manifest.json", "T08_real_behavior": "deferred_by_user", "G1": "incomplete", "limits": ["Legacy v1 fields remain declared-check scores; task score is null without admission.", "T17 downstream legacy migration is separate. Review authenticity/completeness is trusted, not inferred."]}

No server, model/API call, push or external benchmark result. T08 real behavior remains explicitly deferred. Historical evidence and user notes preserved.


### Hardening T11 local completion (2026-10-24)

{"schema_version": "hardening-t11-v1", "status": "completed", "base_commit": "2eb3938b064987f44a48b0755beb151dc3e8ba78", "implementation_commit": "commit containing manifest; exact tested sources hashed in evidence", "completed_at": "2026-10-24T06:44:59.420276+00:00", "scope": "offline authored engineering cases; no server/model/API/external benchmark", "red": {"passed": 0, "failed": 24, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T11-red/20261024T064023169420Z"}, "focused": {"passed": 120, "failed": 0, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T11-final-focused/20261024T064344594182Z"}, "new_tests": 30, "tested_source_hashes_match": true, "evidence": "project_artifacts/results/hardening-v2/T11/20261024T064458800796Z", "bundle": "project_artifacts/results/hardening-v2/T11/20261024T064458800796Z/bundle/manifest.json", "T08_real_behavior": "deferred_by_user", "G1": "incomplete"}

No server, model/API call, push or external benchmark result. T08 real behavior remains explicitly deferred. Historical evidence and user notes preserved.


T10-T12 delivery review: reviewed requirement coverage is separate from check completion; invalid checks never become artifact defects; content matches cannot escape the frozen location. T11 wider validation exposed two old test contracts using the pre-adaptation hash; fixtures now freeze spec_from_task(task), preserving runtime hash enforcement. T12 first red had a renamed-style fixture lookup problem; corrected red rerun is the official baseline. First green exposed a recursive grouped-shape return-type bug, corrected before final focused/full runs. All earlier attempts remain retained. Final full442 passed/5 known R03/R04/R05/R10/R11 failures/0 errors/0 skips; exit1 preserved. Exact tested source hashes verified. No xfail/skip/suppression. Legacy v1 score consumers migrate in T17; text existence does not establish visibility or recalculated values. No server, live model, push, PR or merge.


### Hardening T12 local completion (2026-10-24)

{"schema_version": "hardening-t12-v1", "status": "completed", "base_commit": "425f3b78928a5ae3749f76ee9c01b590d74b1865", "implementation_commit": "commit containing manifest; exact tested sources hashed in evidence", "completed_at": "2026-10-24T06:54:36.108089+00:00", "scope": "offline authored engineering cases; no server/model/API/external benchmark", "red": {"passed": 4, "failed": 25, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T12-red/20261024T064651892281Z"}, "focused": {"passed": 156, "failed": 0, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T12-final-focused/20261024T065032351708Z"}, "new_tests": 35, "tested_source_hashes_match": true, "evidence": "project_artifacts/results/hardening-v2/T12/20261024T065433339082Z", "bundle": "project_artifacts/results/hardening-v2/T12/20261024T065433339082Z/bundle/manifest.json", "T08_real_behavior": "deferred_by_user", "G1": "incomplete", "full_validation": {"passed": 442, "failed": 5, "error": 0, "skipped": 0, "exit_code": 1, "evidence": "project_artifacts/results/hardening-v2/T12-final-full/20261024T065143066459Z"}, "expected_open": ["R03", "R04", "R05", "R10", "R11"], "limits": ["Legacy v1 total/acceptance fields are declared-check compatibility; task score requires reviewed coverage. T17 consumer migration remains pending.", "Text extraction does not prove rendered visibility (T15) or formula recalculation (T13).", "Scope limits and ambiguous identities produce explicit NEEDS_REVIEW; no truncated pass.", "No real model, renderer, external benchmark or server qualification is claimed."]}

No server, model/API call, push or external benchmark result. T08 real behavior remains explicitly deferred. Historical evidence and user notes preserved.


### T14 local delivery (2026-10-24)

{"schema_version": "hardening-t14-v1", "status": "completed", "local_status": "completed", "base_commit": "ada9f84da1ca8b077792cf0e7b281e8a98bd4899", "implementation_commit": "commit containing manifest; exact source hashes in test records", "completed_at": "2026-10-24T07:20:15.451489+00:00", "scope": "local authored engineering tests; no server/model/API calls", "red": {"passed": 0, "failed": 16, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T14-red/20261024T071549541146Z"}, "focused": {"passed": 91, "failed": 0, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T14-final-focused/20261024T071924229952Z"}, "evidence": "project_artifacts/results/hardening-v2/T14/20261024T072013908473Z", "bundle": "project_artifacts/results/hardening-v2/T14/20261024T072013908473Z/bundle/manifest.json", "A1_cleanup": "blocked_by_automatic_policy_no_deletion", "G1": "incomplete"}

No server/model calls; A1 deletion automatically rejected, no files removed. Earlier failed attempts retained.


### T13 local delivery (2026-10-24)

{"schema_version": "hardening-t13-v1", "status": "partial", "local_status": "completed", "base_commit": "f9730d4607ab3e57f0a091455eeba89e978a53eb", "implementation_commit": "commit containing manifest; exact source hashes in test records", "completed_at": "2026-10-24T07:26:36.209598+00:00", "scope": "local authored engineering tests; no server/model/API calls", "red": {"passed": 2, "failed": 16, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T13-red/20261024T072137963641Z"}, "focused": {"passed": 118, "failed": 0, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T13-final-focused/20261024T072520017590Z"}, "evidence": "project_artifacts/results/hardening-v2/T13/20261024T072632724385Z", "bundle": "project_artifacts/results/hardening-v2/T13/20261024T072632724385Z/bundle/manifest.json", "A1_cleanup": "blocked_by_automatic_policy_no_deletion", "G1": "incomplete", "real_qualification": "deferred_by_user_not_run"}

No server/model calls; A1 deletion automatically rejected, no files removed. Earlier failed attempts retained.


### T15 local delivery (2026-10-24)

{"schema_version": "hardening-t15-v1", "status": "partial", "local_status": "completed", "base_commit": "b9598c4effd4c2e8c3e32306b847bcc70eeeac81", "implementation_commit": "commit containing manifest; exact source hashes in test records", "completed_at": "2026-10-24T07:37:15.802924+00:00", "scope": "local authored engineering tests; no server/model/API calls", "red": {"passed": 1, "failed": 17, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T15-red/20261024T072729925670Z"}, "focused": {"passed": 182, "failed": 0, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T15-final-focused/20261024T073426154983Z"}, "evidence": "project_artifacts/results/hardening-v2/T15/20261024T073714709166Z", "bundle": "project_artifacts/results/hardening-v2/T15/20261024T073714709166Z/bundle/manifest.json", "A1_cleanup": "blocked_by_automatic_policy_no_deletion", "G1": "incomplete", "real_qualification": "deferred_by_user_not_run", "full_validation": {"passed": 512, "failed": 2, "error": 0, "skipped": 0, "exit_code": 1, "evidence": "project_artifacts/results/hardening-v2/T15-final-full/20261024T073436079821Z"}, "expected_open": ["R10", "R11"]}

No server/model calls; A1 deletion automatically rejected, no files removed. Earlier failed attempts retained.


### T16 local delivery (2026-10-24)

{"schema_version": "hardening-t16-v1", "status": "partial", "local_status": "completed", "base_commit": "d5239444a9ccebaf1496aec39b55670eaa42d695", "implementation_commit": "commit containing manifest; exact sources in test records", "completed_at": "2026-10-24T10:15:08.905534+00:00", "scope": "local authored engineering tests; no remote server/model/API calls", "red": {"passed": 0, "failed": 18, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T16-red/20261024T085207852225Z"}, "focused": {"passed": 99, "failed": 0, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T16-final-focused/20261024T090751092963Z"}, "evidence": "project_artifacts/results/hardening-v2/T16/20261024T101507439756Z", "bundle": "project_artifacts/results/hardening-v2/T16/20261024T101507439756Z/bundle/manifest.json", "G1": "incomplete", "real_qualification": "deferred_by_user_not_run"}

Real server/model capability remains unqualified by these authored tests.


### T17 local delivery (2026-10-24)

{"schema_version": "hardening-t17-v1", "status": "completed", "local_status": "completed", "base_commit": "571f14fe37760fb5517718699ff3117718792fbc", "implementation_commit": "commit containing manifest; exact sources in test records", "completed_at": "2026-10-24T10:27:35.912540+00:00", "scope": "local authored engineering tests; no remote server/model/API calls", "red": {"passed": 0, "failed": 11, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T17-red/20261024T101750510688Z"}, "focused": {"passed": 141, "failed": 0, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T17-final-focused/20261024T102403860937Z"}, "evidence": "project_artifacts/results/hardening-v2/T17/20261024T102734939310Z", "bundle": "project_artifacts/results/hardening-v2/T17/20261024T102734939310Z/bundle/manifest.json", "G1": "incomplete"}

Real server/model capability remains unqualified by these authored tests.


### T18 local delivery (2026-10-24)

{"schema_version": "hardening-t18-v1", "status": "completed", "local_status": "completed", "base_commit": "67c75cb20b213352774c40dfb231507ff711b8f5", "implementation_commit": "commit containing manifest; exact sources in test records", "completed_at": "2026-10-24T10:59:55.949425+00:00", "scope": "local authored engineering tests; no remote server/model/API calls", "red": {"passed": 1, "failed": 13, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T18-red/20261024T102841289200Z"}, "focused": {"passed": 207, "failed": 0, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T18-final-focused/20261024T105559998584Z"}, "evidence": "project_artifacts/results/hardening-v2/T18/20261024T105955004559Z", "bundle": "project_artifacts/results/hardening-v2/T18/20261024T105955004559Z/bundle/manifest.json", "G1": "incomplete", "full_validation": {"passed": 569, "failed": 2, "error": 0, "skipped": 0, "exit_code": 1, "evidence": "project_artifacts/results/hardening-v2/T18-final-full/20261024T105610295802Z"}, "expected_open": ["R10", "R11"]}

Real server/model capability remains unqualified by these authored tests.


### T13 actual server qualification (2026-10-24)

14 actual isolated LibreOffice runs passed with independent arithmetic oracles, five input variants, negative controls and unchanged originals. No model calls or new runtime installation. Evidence: `project_artifacts/results/hardening-v2/T13-real/20261024T122504362212Z`. Scope is the frozen engine and authored cases, not general equivalence.


### T08 actual behavior qualification (2026-10-24)

Preserving candidate passed three authored tasks; first-two-entries control regressed on two protected cases and was rejected. Actual RSI route reran behavior and preserved champion. Three accepted model generations used codex-cli gpt-6.1-sol; no generated code ran on the host. Frozen generation snapshots and cached real parent baseline do not constitute a full live RSI benchmark. Evidence: `project_artifacts/results/hardening-v2/T08-real/20261024T123719407816Z`, `project_artifacts/results/hardening-v2/T08-rsi-real/20261024T123929807716Z`. Earlier CLI startup/configuration and warning-classification failures are retained separately and charged against the same budget.


### T15/T16 actual probe and discovered scope regression (2026-10-24)

24 actual rendered pages and six visual controls passed; joint-image review passed. Semantic authorized-source, contradiction, injection, cache and independent review contracts passed with real CLI gpt-6.1-sol. The17-page result conservatively requested review due to incorrect whole-document scope in individual batches. Fixed in0b64a04; four new red cases now pass, related suite84 pass. Original budget24 launch reservations exhausted (23 observed model turns, including one rejected warning-classification result). Additional3 requests require explicit user confirmation; not yet executed. T15/T16 remain partial pending this concrete recheck. Pre-fix full suite574 passed/2 known R10/R11 failures.


### T15/T16 actual probe and discovered scope regression (2026-10-24)

24 actual rendered pages and six visual controls passed; joint-image review passed. Semantic authorized-source, contradiction, injection, cache and independent review contracts passed with real CLI gpt-6.1-sol. The17-page result conservatively requested review due to incorrect whole-document scope in individual batches. Fixed in0b64a04; four new red cases now pass, related suite84 pass. Original budget24 launch reservations exhausted (23 observed model turns, including one rejected warning-classification result). Additional3 requests require explicit user confirmation; not yet executed. T15/T16 remain partial pending this concrete recheck. Pre-fix full suite574 passed/2 known R10/R11 failures.


### T15/T16 completed for frozen worker and selected CLI (2026-10-24)

Explicitly approved three-request recheck passed: pages1-8 PASS,9-16 PASS,17 FAIL; all17 pages cited. Scope confusion is fixed and old cache protocol invalidated. T08/T13/T15/T16 deferred qualification is now complete for the recorded Apptainer worker and CLI gpt-6.1-sol profile. Direct API and accuracy calibration are not claimed. {"launch_reservations": 27, "observed_completed_model_turns": 26, "reserved_cumulative_wall_seconds": 429, "input_tokens": 418336, "output_tokens": 5412, "max_observed_output_tokens": 559, "cost_usd": null, "cost_status": "unavailable", "tools_in_retained_accepted_logs": 0, "legacy_conservative_tool_charge": 1, "scope": "24 original +3 explicitly approved launch reservations; original1200s/32tool ceiling retained"}


### T19 trace-grounded diagnosis (2026-10-24)

{"schema_version": "hardening-t19-v1", "status": "completed", "base_commit": "8641499373bcbff7b25481c911bb5ba67b0bd6d0", "implementation_commit": "commit containing this manifest; exact source hashes in focused evidence", "scope": "local trace-grounded engineering; five genuine trusted authored-program failure/artifact cases; no model/server calls", "red": {"failed": 15, "error": 0, "evidence": "project_artifacts/results/hardening-v2/T19-red/20261024T125842394569Z"}, "review_red": {"failed": 5, "passed": 15, "evidence": "project_artifacts/results/hardening-v2/T19-review-red/20261024T130228792851Z"}, "legacy_red": {"failed": 1, "passed": 2, "evidence": "project_artifacts/results/hardening-v2/T19-legacy-red/20261024T130528192260Z"}, "focused": {"passed": 51, "failed": 0, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T19-delivery-focused/20261024T130553728003Z"}, "trace_probe": "project_artifacts/results/hardening-v2/T19-probe/20261024T130436485682Z", "actual_authored_cases": 5, "new_tests": 21, "limitations": ["rule strengths are uncalibrated", "input counts and write receipts require trusted provenance", "not general causal inference"], "expected_open": ["R10", "R11"], "G1": "incomplete", "evidence": "project_artifacts/results/hardening-v2/T19/20261024T130827249534Z", "bundle": "project_artifacts/results/hardening-v2/T19/20261024T130827249534Z/bundle/manifest.json"}


### T20 execution feedback and denominators (2026-10-24)

{"schema_version": "hardening-t20-v1", "status": "completed", "base_commit": "6057b4304407846e2150c3f78077b167a1886354", "implementation_commit": "commit containing this manifest; exact sources bound by focused/full records", "scope": "offline engineering; genuine OOXML, authored execution failures, injected transport failures and actual RSI capture path; no model/server calls", "red": {"passed": 1, "failed": 12, "error": 0, "evidence": "project_artifacts/results/hardening-v2/T20-red/20261024T131203752641Z"}, "integration_review_red": {"passed": 17, "failed": 1, "evidence": "project_artifacts/results/hardening-v2/T20-integration-review/20261024T131911860208Z"}, "resource_red": {"failed": 2, "evidence": "project_artifacts/results/hardening-v2/T20-resource-red/20261024T132207300105Z"}, "metric_review_red": {"failed": 2, "evidence": "project_artifacts/results/hardening-v2/T20-metric-review-red/20261024T132405412808Z"}, "focused": {"passed": 114, "failed": 0, "error": 0, "skipped": 0, "evidence": "project_artifacts/results/hardening-v2/T20-delivery-focused/20261024T132432449518Z"}, "full_validation": {"passed": 620, "failed": 1, "error": 0, "skipped": 0, "exit_code": 1, "evidence": "project_artifacts/results/hardening-v2/T20-delivery-full/20261024T132432256612Z"}, "new_tests": 20, "R11": "passed", "expected_open": ["R10"], "G1": "incomplete", "limitations": ["not a live RSI improvement", "preregistered task-success promotion policy belongs to T29", "unobserved quality stays null"], "evidence": "project_artifacts/results/hardening-v2/T20/20261024T133149608664Z", "bundle": "project_artifacts/results/hardening-v2/T20/20261024T133149608664Z/bundle/manifest.json"}

## 2026-10-24 T21 task repair

- Implemented opt-in Harness repair, separate execution retries and fresh per-attempt full assessment.
- Retained task/spec, code snapshots, before/after OOXML hashes, reports and trace state; no registry update.
- Red: 9 passed/11 failed/0 errors. Delivery: 55 passed/0 failures/errors/skips. See hardening_t21_repair_loop.json.
- R10 compatibility fixture now explicitly selects legacy declared checks after T17 admission changes. Reviewed acceptance tests independently cover task repair.
- One mistyped test path caused a collection exit4 and was corrected; that attempt is retained. No real model or server calls.

## 2026-10-24 T22 budget and protected repair

- Added shared pre-call reservations for native execution, API retries, tools, judges and API candidate generation. Failed/interrupted requests stay charged; opaque execution/candidate CLI loops are unavailable in bounded mode.
- Bound repair and budget limits to evaluator identity; propagated real split names through Harness. Protected splits and hidden tasks never receive assessment-driven repair requests.
- Retained the best assessed artifacts and rejected attempts; a later environment/transport gap stays incomplete. Added allowed-output checks, no-progress stopping, atomic best-result history and interruption accounting.
- Fixed trace-root binding and preserved exact LF/CRLF source hashes in repair context. Corrected R10 compatibility fixture without relaxing task admission.
- Final focused: 121 passed. Full: 663 passed, 0 failed/errors/skips. R01-R12 pass. Original and relocated bundles verified; exact hashes/counts are in T21/T22 manifests.
- No real model or server calls. Native transport and CLI boundary tests are authored offline qualification. Live repair, active recovery, matched experiment arms and research validation remain later work.
- Ledger recommendations, R10/R11 states, validation and bundle indexes reconciled; older indexes retained as history.

## T23 production prompt independence

Removed fixed answer rules and task-ID strategy selection; retained generic Office knowledge and authorized template inputs. Added explicit execution mode and task binding. Qualification-only fixed implementations are rejected by formal entry points. Red12 failures; focused92 passes. See hardening_t23_prompt_independence.json. No model/server calls.
