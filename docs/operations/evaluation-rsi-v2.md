# 评估与 RSI 的执行和交接

> Historical protocol snapshot. On 2026-10-29 the user replaced coded task acceptance with [task-level LLM review](llm-task-review.md). Rule coverage, rule-authoring commands and per-criterion scoring below are historical records, not current run instructions. Native reading, rendering, transport and experiment controls remain where applicable.

Current update (2026-10-28): see [remaining work](remaining-work-20261028.md). The approved recovery is complete:26 attempts,24 valid decisions,12 full case pairs;567charged seconds/0tools. Natural20 requirements-based follow-up and judging remain pending;both standard interpretations have been clarified. Earlier run descriptions below are historical snapshots.

本文对应 2026-10-26 的本地工程交付。原始计划是 `docs/superpowers/plans/2026-10-16-evaluation-rsi-hardening.md`，共 T00 至 T35。实际状态以 `project_artifacts/formal_study/hardening_task_ledger.json` 和对应证据为准。

当前已冻结 judge v2 请求，整理 72 个 T31 未审阅验收草案，并接收用户完成的六例复核。13 项接收与来源校验测试、4 项未发送请求续跑测试通过。用户批准 v2 后累计运行 16 次请求，取得 14 个有效判定、6 个完整案例，第 11、16 次 HTTP 429。续跑只发送原清单中未尝试的请求，共用原账本，失败项均未重试；未运行服务器作业。当前结果见 `project_artifacts/formal_study/hardening_t28_judge_v2_delivery.json`；T28 仍未完成，六例无需重复复核。

下文 773 项 Windows／149 项 Linux 和完整发布门禁属于此前工程验收快照，不能视为后来准备工具及接收模块变更后的新一轮全量验收。

## 当前可用能力和声明范围

普通任务仍从 `Harness` 进入。执行器生成真实 Excel、Word、PowerPoint 文件，固定评估器按事先声明的要求检查内容、结构、语义或实际渲染页。固定 verifier 给出缺陷位置、证据和修复建议。任务内修复只修改本次产物；外循环只允许修改执行技能的 `instructions`，不能修改任务、评估规则或保护集。

请区分三种覆盖：任务要求是否被完整表达、检查是否具备能力并实际完成、视觉渲染是否覆盖必要页面。某个字段或几个页面通过，不能证明整份任务完成。缺失能力、规格歧义、模型接口失败属于环境或评估缺口；有证据的执行错误和产物缺陷才计入对应失败。模板只用于工程验证，不能当作新任务上的真实模型收益。

T29 新比较模式执行三次独立重复，按重复轮次交替基线和候选，保留失败和全部分母。成功执行后的质量均值包含所有重复；有有效的执行失败时改用任务成功率，包括产物验收失败。按任务家族做配对 bootstrap，提升必须大于 0.05，95% 区间下界大于零；保护集逐领域检查不超过 0.01 的退化，关键要求不允许退化。执行和质量方差分别报告，单独的 judge 方差没有被识别，保留 null。缓存模型判定不算独立重复。

原有契约没有 `comparison_policy` 时，保持历史协议。新模式只控制工程版本选择，始终不自动授予研究资格。候选没有通过独立行为验证时会被拒绝；拒绝也可以证明外循环管线完整运行。

## 仍待完成的验收

- T26 当前候选是 Excel、Word、PPT 各 24 个，共 72 个基础任务和 72 个原始实例。尚缺原计划的其他 144 个合格实例、独立封存的 final 和独立评估账号。PPT 输入主要是原图/PDF，任务要求输出可编辑 PPTX，不能称为 24 份已有 PPTX 输入。
- T28 已接收用户的 32 条实际标签：29 PASS、2 FAIL、1 PARTIAL。用户说明主要是快速浏览，记录为初步判断；不能直接用于计算 evaluator 的误判率。重复任务的原因及六个优先核对的标准例见 [复核说明](human-review-follow-up-20261026.md)。已批准的 12 标准例 judge 试运行发出 6 次请求，取得 5 个通道判定，第 6 次 HTTP 429 后停止；尚未完成完整校准。两个自然 Excel 例仍有原始渲染覆盖缺口。原始提交与审阅包均保留。
- T29 的真实重复对照仍待合格数据、评估器和新调用预算。离线 fixture 的统计信号不是模型能力结论。
- T31 已有默认关闭的配置、预检、冻结清单、真实 runner 路径和显式 resume。尚未进行本轮真实三域自然失败、修复、复评的资格运行，也未完成 T28 的 judge 校准。
- 现有 72 项输入已转换成 `project_artifacts/results/hardening-v2/T31-prepared/20261026/task-bundle.draft.json`，同时保存输入哈希与家族绑定。72 项的完整任务验收规格均仍为 SPEC_INCOMPLETE；不能直接把这份结构草稿当作合格的评估任务集运行。
- T32 已有四组预注册、相同预算上限、不可覆写的组别记录、固定参考集和 final 一次性门禁、可信 backend 的四组调度接口。当前生产接口没有合格的总 token 硬限制，未注册可用的四组生产 backend，CLI 明确阻断真实调度。不能只把请求数相等称为 token 预算相等。
- T33 已有准入报告和分离的原生/自定义评分通道。现有服务器 LibreOffice 与原 benchmark 环境不一致，不能声明原生评分环境对齐；同账号下的目录隔离也不等于独立评估账号。
- T34 分开报告 `engineering_pass`、`live_loop_pass`、`research_pass`、`external_pass`。本轮补齐选定 Linux 非 COM 检查，工程门禁通过；人工校准、真实闭环和外部证据仍不完整，后三级保持 false。

当前 `cluster_vlab_jump` 连接已恢复。使用现有 Apptainer 镜像完成 149 项选定 Linux 非 COM 检查及 19 个自然 Excel 重算作业，没有安装服务器包或修改镜像。测试依赖从约 24.88 MB 的本地归档导入临时工作区，源码和依赖展开约 43.92 MB，结束后清理。现有镜像约 696 MB，未为本轮增加镜像。Linux 作业内存限制为 2 GB，CPU 为 2。历史模型额度没有复用；本轮单独批准的上限为 24 次请求、0 工具、1200 秒，实际发出 6 次后因 429 停止，没有自动重试或扩额。

当前代码的最终验证为 Windows 773 项测试通过、0 失败；Linux 上选定的 149 项非 COM 检查通过，这不是 Linux 全量测试。90 例确定性校准为 45 PASS、28 FAIL、17 INCOMPLETE，已知误接收和等价方案误拒绝均为 0；这些是三个相关家族上的开发检查，不能当作总体准确率。三域证据包换目录、删除临时原输入后重新评估通过，使用当前评估器身份，没有复用旧分数。代码与测试哈希和最终测试记录一致。当前发布门禁见 `project_artifacts/results/hardening-v2/T34-human-release/20261026/release-gate.json`；旧 `T34-local` 记录保留为当时的状态。

## 可直接检查的命令

以下命令从项目根目录执行。当前 Windows 环境使用 `.venv\Scripts\python.exe`。`--help` 和下面两条 `--dry-run` 不调用模型，也不连接服务器。

```powershell
.venv\Scripts\python.exe -m workagent_rsi.cli --help
.venv\Scripts\python.exe skills/office-artifact-evaluator/scripts/evaluate.py --help
.venv\Scripts\python.exe skills/office-artifact-verifier/scripts/verify.py --help
.venv\Scripts\python.exe project_artifacts/phase3_experiments/scripts/calibrate_evaluator.py --help
.venv\Scripts\python.exe project_artifacts/phase3_experiments/scripts/prepare_human_calibration.py --help
.venv\Scripts\python.exe project_artifacts/phase3_experiments/scripts/run_qualification_v2.py --dry-run
.venv\Scripts\python.exe project_artifacts/phase3_experiments/scripts/run_comparison_v2.py --dry-run
.venv\Scripts\python.exe project_artifacts/phase3_experiments/scripts/check_external_admission_v2.py --help
.venv\Scripts\python.exe project_artifacts/phase3_experiments/scripts/validate_release_v2.py --help
.venv\Scripts\python.exe project_artifacts/phase3_experiments/scripts/run_formal.py --help
```

普通执行的具体任务入口：

```powershell
.venv\Scripts\python.exe -m workagent_rsi.cli path/to/task.json --results-dir project_artifacts/results/my-task
```

涉及模型的普通执行仍需先具备相应的运行环境和调用授权。任务内修复通过 Python 接口传入 `RepairPolicy` 与共享 `RunBudget`，没有独立的“自动无限重试”命令。

T31 配置里的路径以当前工作目录为基准。`tasks_file` 必须包含 `splits` 和 `family_manifest`：四个 split 为 develop、regression、hidden、ood_transfer，每个覆盖三个领域；hidden 在适应性开发中表示 promotion_validation。final 数据不能进入这里。还需提供初始技能、WorkAgent 配置、评估配置、哈希绑定的能力回执、sandbox digest 和新的调用策略。顶层模型/endpoint 必须与执行器配置一致。

```powershell
.venv\Scripts\python.exe project_artifacts/phase3_experiments/scripts/run_qualification_v2.py --config path/to/approved-config.json --dry-run
# 仅在预检通过且新预算已获批准后执行：
.venv\Scripts\python.exe project_artifacts/phase3_experiments/scripts/run_qualification_v2.py --config path/to/approved-config.json
.venv\Scripts\python.exe project_artifacts/phase3_experiments/scripts/run_qualification_v2.py --config path/to/approved-config.json --resume path/to/run-root
```

预检显示硬调用上限和可能的提前耗尽，并不保证现有上限足够跑完任务。配置变更必须建立新 cohort。恢复会检查数据、规格、评估器、执行技能、候选接口配置和代码身份；完成轮次不重新执行，未完成轮次建立新的 attempt。预算恢复保留失败和中断请求，未知 token/费用继续为空，离线暂停期间不计活动运行时间。

## 材料、结果与回滚

当前审阅页面：`project_artifacts/results/hardening-v2/T28-benchmarks/20261025/complete-human-pack-v1/blind-review-pack/index.html`。当前均衡候选清单：`project_artifacts/results/hardening-v2/T26-balanced/20261026/cohort-v2/evaluator-only/task-manifest.json`。后者含评估侧信息，不应整体提供给执行模型。

本轮改动以分阶段本地 commit 保存，未 push。历史基线 `d07f9c2`、首批集成 `334e04f` 可用于比较。查看 `git log --oneline` 后选择要回滚的提交；在工作区干净并确认依赖的情况下使用 `git revert <commit>`，保留反向修改记录。不要删除结果目录或数据库来“回滚”。

运行技能回滚使用 `RollbackManager(SkillRegistry(registry_root)).rollback(skill_id, target_version, evidence_refs)`，只切换 champion alias 并追加回滚记录。包内容按哈希保存，拒绝证据按父包哈希、任务批次和补丁哈希隔离。不要重写历史版本。旧报告可读取，但升级后的代码身份与旧 checkpoint 不一致时应拒绝恢复并创建新运行。

外部评分分别输出 `native_benchmark` 和 `custom_artifact_quality`。许可证、来源、哈希、评估器版本、执行/评估边界或原生环境一致性缺一，正式外部声明被阻止。自定义评分不能改名为原 benchmark 成绩。
