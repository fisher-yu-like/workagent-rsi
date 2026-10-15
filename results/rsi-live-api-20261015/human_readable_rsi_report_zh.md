# 真实 RSI 外循环结果（2026-10-15）

## 结论

本轮使用真实非 Ollama provider，完成了四个非空 split 的 baseline、真实 candidate 生成、candidate evaluator、CandidateVerifier 和 promotion gate。candidate 没有被晋级，因为 develop 分数没有提升；系统正确拒绝了它，没有替换 champion。

## 实验配置

- WorkAgent provider：`openai-chat:deepseek-v4-flash`
- Candidate provider：`openai-chat:claude-fable-5-1`
- split：`develop`、`regression`、`hidden`、`ood_transfer`，每个 1 个任务
- 每个任务重复 2 次；COM reopen 关闭
- evaluator identity：`e44e4887ea91c1424306d0f1f1c60a15a311d9bbb39e4b94d943e0b136743097`

## 分数对比

| split | baseline | candidate | baseline success | candidate success |
|---|---:|---:|---:|---:|
| develop | 1.0 | 1.0 | 1.0 | 1.0 |
| regression | 1.0 | 1.0 | 1.0 | 1.0 |
| hidden | 1.0 | 1.0 | 1.0 | 1.0 |
| ood_transfer | 1.0 | 1.0 | 1.0 | 1.0 |

## Candidate 结果

- Candidate ID：`office-skill-instructions-reuse-001`
- CandidateVerifier：`PASS`，执行检查：path_policy, leakage, patch_schema, compile
- provider 状态：`completed`，模型：`openai-chat:claude-fable-5-1`
- promotion：`reject`
- quality delta：`0.0`
- rejection 原因：quality gate 未通过，因为 develop 从 1.0 到 1.0，没有超过要求的 0.05 提升。
- regression、hidden、OOD 均无回退，critical regression 为 0。

## 证据路径

- 首轮 outer-loop summary：`C:\Users\sy\Desktop\workagent-rsi\worktrees\office-artifact-assessment-merge\results\rsi-live-api-20261015\experiment\summary.json`
- checkpoint：`C:\Users\sy\Desktop\workagent-rsi\worktrees\office-artifact-assessment-merge\results\rsi-live-api-20261015\experiment\rounds\checkpoint.json`
- baseline：`C:\Users\sy\Desktop\workagent-rsi\worktrees\office-artifact-assessment-merge\results\rsi-live-api-20261015\experiment\rounds\round-01\baseline`
- candidate evaluator：`C:\Users\sy\Desktop\workagent-rsi\worktrees\office-artifact-assessment-merge\results\rsi-live-api-20261015\experiment\rounds\round-01\candidate-retry-fable`
- candidate provider record：`C:\Users\sy\Desktop\workagent-rsi\worktrees\office-artifact-assessment-merge\results\rsi-live-api-20261015\experiment\rounds\round-01\provider_records-retry-fable-4`
- verifier：`C:\Users\sy\Desktop\workagent-rsi\worktrees\office-artifact-assessment-merge\results\rsi-live-api-20261015\experiment\rounds\round-01\candidate-retry-fable\verification.json`
- promotion：`C:\Users\sy\Desktop\workagent-rsi\worktrees\office-artifact-assessment-merge\results\rsi-live-api-20261015\experiment\rounds\round-01\candidate-retry-fable\decision.json`

## 真实错误及处理

- 首次 candidate 调用使用 `deepseek-v4-flash`，网关连续返回 HTTP 429，outer loop 正确记录为 `incomplete`，没有伪造 candidate 或晋级。
- 使用另一已验证支持 JSON/tool 调用的非 Ollama模型 `claude-fable-5-1` 重试；模型返回了不同但结构相近的 CandidatePatch envelope，provider 增加了严格归一化并保留原始 response。
- 归一化后的 patch 仅修改 `skill.json` 的 `instructions` 字段，并通过 CandidateVerifier。

## 范围限制

- 本轮 assessment 是 artifact-v1 结构/内容/公式/格式检查；semantic/visual 通道为空。
- COM reopen 为 disabled。
- candidate 被拒绝是有效 RSI 结果，champion 保持 `1.0.0`。
