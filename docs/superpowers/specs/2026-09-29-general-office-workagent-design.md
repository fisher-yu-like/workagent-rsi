# 通用 Office WorkAgent 执行器设计规格

## 目标与范围

当前 Office adapter 只能套用固定模板写标题和标记，不理解任务内容。本设计把它升级为真正的通用执行器：本机 Codex CLI 调用 Ollama 模型，在每次任务专属的工作区里阅读自然语言要求与输入文件副本，编写并运行 Python，创建或编辑 Excel、Word、PowerPoint 文件；Harness 接收产物、保存证据、执行文件评估，并由 Microsoft Office COM 重开验证。

首版支持：

- 从零创建 `.xlsx`、`.docx` 或 `.pptx`；
- 基于用户提供的 Excel、Word、PowerPoint 输入副本生成编辑后的新文件；
- 每次 Harness 调用只处理一个 Office 主域，可有多个同域输入及多个输出。

首版不声称覆盖所有 Office 功能，不自动给主观视觉质量打分，不进行模型权重训练。

## 已确认的硬边界

- 输入原件只读并复制到当前运行目录；模型只能收到副本路径。原件不被覆盖，运行前后对原件计算 SHA-256，发生变化则记录安全失败。
- 只接收 `agent_workspace/outputs/` 内、清单所列并通过路径/类型/结构检查的文件。
- 模型调用失败、超时、无产物或产物不合格时明确失败；绝不回退到模板 Office adapter。
- 默认任务执行使用本地 Ollama `qwen2.5:7b`，模型和 CLI 路径可配置；记录身份取自命令配置而非模型自报。
- 每次运行单独保存 prompt、模型输出、stdout/stderr、输入/输出清单、trace、文件、评估与 Office 重开记录，全部位于 `project_artifacts/results/<run-id>/`。
- 自动化测试只放在现有顶层 `tests/`；pytest 临时文件显式放到结果目录中的隔离临时位置，保持项目主目录整洁。
- 本机 Codex CLI `0.157.1`、Ollama `0.34.4`、模型 `qwen2.5:7b` 和三种 Office COM `16.0` 已核实。Docker daemon 不可用；首版仅采用 Codex 的 `workspace-write` 沙箱，不声称容器级或抵抗恶意输入的强隔离。

## 执行架构

公开入口仍为 `Harness.run(task)`。`Run` 对 Office 域默认选择真实 `workagent` provider；若 Codex/Ollama 不可用则返回 `UNAVAILABLE`，不能选择模板器兜底。`local_office`、`com` 和 `smoke` 保留作确定性测试/兼容 provider，必须显式指定。

在现有 `Run -> Orchestrator -> Adapter -> Evaluator` 链路中新增集中的 `WorkAgentOfficeAdapter`，不在 Orchestrator 中直接放 CLI 细节。集中配置项为：`model="qwen2.5:7b"`、`executable="codex"`、`timeout_seconds=600`、`max_output_files=8`、`max_artifact_bytes=100 MiB`。Adapter 接收 `run_root`、该配置和可注入的 subprocess runner，提供与现有 Office adapter 一致的 `execute(task, skill_id) -> Iterable[event]` 接口。

实际子进程使用已核实可用的 Codex CLI 参数：

```text
codex exec --ignore-user-config --oss --local-provider ollama
  --model <configured-model> --ephemeral --sandbox workspace-write
  --json --output-schema <response-schema.json>
  --output-last-message <run-dir/agent_response.json>
  --cd <run-dir/agent_workspace> <prompt>
```

如果某个已安装 CLI 版本不接受必需参数，provider 返回 `UNAVAILABLE` 并保存命令/错误证据，不执行无沙箱调用。`runner` 可注入测试桩；生产默认 runner 使用显式 UTF-8、timeout、stdout/stderr 捕获，并在超时时终止该 Codex 子进程。

## 单轮数据流

```text
TaskSpec
  -> 创建唯一 run 目录
  -> 校验输入路径/格式、复制 inputs/、保存 input_manifest.json
  -> 创建 outputs/ 并写入任务 prompt
  -> Codex CLI + 本机 Ollama 在 workspace-write 沙箱中工作
  -> 校验结构化 agent_response.json 和 deliverables.json
  -> 检查输出路径、扩展名、文件大小、OOXML 和库级可读性
  -> 可选 Office COM 只读重开
  -> artifact store + OfficeArtifactEvaluator + result.json + trace.db
```

每个运行目录至少包含：`task.json`、`input_manifest.json`、`prompt.md`、`provider.stdout.jsonl`、`provider.stderr.txt`、`agent_response.json`、`deliverables.json`、`trace.db`、`artifacts/`、`evaluation.json`、`result.json` 和 `run_report.md`。失败运行也保留同等目录与真实失败证据。

## 输入文件规则

- `TaskSpec.input_files` 是用户明确提供的文件列表。绝对路径按该项的明确授权读取；相对路径相对于调用方声明的输入基准目录，Harness API 默认为调用工作目录，CLI 以 task YAML 所在目录为基准。
- 只接受本机普通文件；拒绝目录、符号链接、路径遍历和不匹配任务域的扩展名。UNC/网络路径不在首版支持范围。
- 输入复制至 `agent_workspace/inputs/<序号>-<安全文件名>`。清单只记录源文件名标签（不写本机绝对路径）、副本相对路径、文件大小、SHA-256 和时间；`task.json` 同样保存去除本机绝对路径后的输入映射。
- 模型只能收到 `inputs/` 中的副本路径；输出写到 `outputs/`。不得把原始绝对路径或凭据放入模型 prompt。
- `TaskSpec.expected_constraints` 是评估器侧信息，不传给 WorkAgent；WorkAgent 只看到任务指令和输入副本信息，避免把基准检查答案泄漏给被测执行器。

## Prompt 与产物契约

Prompt 包含任务域、用户指令、输入文件映射、输出目录、可用 Python Office 库和边界：只在工作区操作，不访问父目录、仓库敏感数据、隐藏评估文件或网络资源；输入源不覆盖；生成后重新打开并自检。prompt 不包含 `expected_constraints`、评估分数、隐藏标签或 RSI 晋级阈值。

Codex 最终响应遵守 CLI `--output-schema`，并与工作区中的 `deliverables.json` 一致：

```json
{
  "status": "completed",
  "deliverables": ["outputs/report.xlsx"],
  "summary": "创建了月度汇总表",
  "input_files_used": ["inputs/0001-source.xlsx"]
}
```

Harness 拒绝格式错误、相互冲突、路径越界、遗漏文件或空文件；不猜测、不扫描任意目录后替模型挑产物。只接受任务主域对应的 `.xlsx`、`.docx` 或 `.pptx`，最大文件数和每文件大小受配置限制。

## Adapter 事件与状态

WorkAgent adapter 发出 `started`、`input_manifest`、`provider_output`、每个已验证的 `artifact`，以及 `failure`/`unavailable`/`timeout` 事件。事件记入 SQLite trace；大体积输出保存在同一 run 目录并以哈希引用。

- CLI 不存在、Ollama/model 不可用、沙箱参数不可用：`UNAVAILABLE`；
- 子进程超时：`TIMEOUT`，保留 partial stdout/stderr，不计入分数；
- 模型结构化响应非法、没有交付、路径/格式/结构错误：`FAILED`；
- Office evaluator 或显式 COM 重开失败：`FAILED`；
- 只有所有必需交付物通过本次任务的硬约束和格式门禁才是 `SUCCEEDED`。

输入原件哈希变化优先于普通成功结果，最终状态为安全失败。若配置要求 COM 校验而该应用不可用，COM 通道记录 `unavailable`，该次运行不能被报告为 COM 已验证；当前资格验证配置要求三种 COM 均通过。COM 验证使用只读打开并保留现有 Office 进程；绝不关闭运行前已存在的 Word/Excel/PowerPoint 进程。

## 评估与 RSI 设计

先用我们编写的六项可审计 pilot 评估真实 baseline：Excel、Word、PowerPoint 各一项从零创建及一项输入编辑。任务数据和编辑用输入文件均由仓库内脚本生成，注明 `project-generated`；不是外部 benchmark。

每个任务配明确的机器检查要求，例如工作表/指定单元格/公式、标题/章节/关键文本、幻灯片数量/文本。复用并按需要扩展 `OfficeArtifactEvaluator` 的 OOXML、结构、约束检查；COM 用于文件打开门禁。格式可读、任务约束和视觉渲染分别记录；未配置/不可用的视觉通道不记分。RSI 之前冻结任务分割和 evaluator hash。

通用 provider 基线跑通后，RSI 再接入实际 `WorkAgentOfficeAdapter`，而不是现在仅对 marker 模板评分的 `FrozenEvaluator`。RSI 可改的仅限版本化技能说明/prompt 模板/任务规划配置；不得改 provider 沙箱、文件路径门禁、evaluator、隐藏任务或 promotion policy。候选闭环为：真实运行诊断 → 受限候选 → 文件/泄漏/范围验证 → develop、跨格式 regression 和 OOD 冻结复测 → promotion gate 接受或拒绝。未观察到可改进的真实问题时不制造失败；不可用/超时结果不充当零分。

该 RSI 首轮只报告工程 pilot，不报告模型权重训练或外部 benchmark 结论。正式外部数据仍须独立通过来源、许可证、质量与泄漏门禁。

## 验收标准

1. Harness 的 Office 正常路径调用 WorkAgent；模型不可用时无模板器回退。
2. TDD 测试覆盖命令构造、JSON/schema、输入复制与原文件哈希、路径逃逸、格式错配、大小/数量限制、timeout/unavailable、无产物和 trace 状态。
3. 六个真实 pilot 任务（3 种格式 × 创建/编辑）都运行并保留结果；任何实际失败均留在证据中，不隐藏或伪报通过。只有三种格式的创建任务和编辑任务都至少各有一次成功，才进入 RSI；否则先诊断执行器并保留失败记录。
4. 每个 Office 文件通过对应 Python 库和 OfficeArtifactEvaluator；三种格式的创建与编辑产物都通过 Microsoft Office 16.0 COM 重开。
5. 每项编辑任务源输入文件 SHA-256 运行前后一致。
6. 用户自建 pilot 的任务约束结果、哈希、prompt、模型配置、耗时和评估器版本均可追溯；不可用通道不转成分数。
7. pytest 只使用顶层 `tests/`，用 `--basetemp` 指向 `project_artifacts/results/` 下的一处临时目录，并关闭根目录 pytest cache；不新建根目录测试文件夹。
8. 上述通用 WorkAgent 验收结束后，才用相同执行器运行真实 RSI pilot，并保存每轮候选、验证、接受/拒绝、成本和范围声明。

## 明确不包含的能力

- 宏、VBA、COM UI 自动化作为生成器、复杂外链、实时协作和任意 Office XML 功能；
- 容器/虚拟机强隔离或对恶意 Office 文档、提示注入的安全承诺；
- 未经任务验证的主观质量单一分数。
