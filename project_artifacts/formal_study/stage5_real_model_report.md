# 阶段 5 真实模型 RSI Pilot 报告

## 一句话结论

项目已经用本地 Ollama 的 `qwen2.5:7b` 通过 Codex CLI 完成一次可复现的六轮 E05 RSI pilot。第 1 轮候选通过验证并晋级，之后 5 个候选没有带来可接受的额外收益或未通过 patch 验证；develop 分数从 `0.0` 提升到 `1.0`。这是一条真实的候选生成与自动验证记录，不是更新模型权重，也不是外部 benchmark 主结果。

## 运行配置

- 数据：项目生成的 pilot fixture，不含外部任务文件。
- 实验：E05，六轮，编辑预算 `[3, 3, 2, 2, 1, 1]`。
- Provider：Codex CLI `0.158.0-alpha.2.1`，本地 Ollama `qwen2.5:7b`。
- 结果目录：`project_artifacts/results/qualification/real-model/real-e05-qwen25-20260928-final-retry1/`。
- 每轮都保存 provider record、candidate patch、baseline/candidate evaluator report、verification、decision、checkpoint 和 cost。

## 逐轮结果

| 轮次 | 决策 | develop 变化 | 说明 |
|---|---|---:|---|
| 1 | accept | `+1.0` | 候选通过 develop、hidden、OOD、regression 和安全门，`0.1.0 -> 0.2.0` |
| 2 | reject | `0.0` | 没有额外 develop gain |
| 3 | reject | `-1.0` | provider patch 不是合法 JSON，验证器拒绝 |
| 4 | reject | `-1.0` | provider patch 不是合法 JSON，验证器拒绝 |
| 5 | reject | `0.0` | 没有额外 develop gain |
| 6 | reject | `-1.0` | provider patch 不是合法 JSON，验证器拒绝 |

最终 champion 是 `0.2.0`；被拒绝候选仍写入 registry 的 negative evidence，不会覆盖 champion。

## 解释边界

`analysis.json` 明确设置 `claims_allowed=false`。因此本结果只能说明真实 provider、六轮 checkpoint/resume、候选隔离、自动 evaluator、验证器和晋级控制链路已经运行；不能据此声称外部 Office benchmark 提升、通用能力提升或人工标注一致性。token、tool call、step 和 render 成本通道在当前 Codex CLI provider 中不可用，结果中明确记录为 `unavailable`，不会被当成零成本或零调用。

外部正式实验仍被阶段 4 的来源、许可证、checksum、质量和泄漏门禁阻断；在门禁通过前，formal runner 不会下载或运行外部 workbook。

## 证据索引

- 阶段 manifest：`project_artifacts/formal_study/stage5_manifest.json`
- 机器分析：`project_artifacts/results/qualification/real-model/real-e05-qwen25-20260928-final-retry1/analysis.json`
- 六轮 checkpoint：`project_artifacts/results/qualification/real-model/real-e05-qwen25-20260928-final-retry1/E05/e05/round/checkpoint.json`
- 实时日志：`project_artifacts/execution_log.md`
