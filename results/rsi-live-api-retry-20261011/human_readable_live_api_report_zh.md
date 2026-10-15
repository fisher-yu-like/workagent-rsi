# 真实 API Office 端到端结果（2026-10-11）

## 结论

三项任务均由 `openai-chat:deepseek-v4-flash` 真实工具调用生成 Office 产物；Harness、ArtifactEvaluator 和 ArtifactVerifier 均完成。三个结果均为 PASS、100 分、0 个 verifier issue。COM reopen 在这些运行中主动关闭，因此本报告不把 COM 复开验证计入完成范围。

## 结果汇总

| 格式 | Harness 状态 | 产物 | 评分 | 覆盖 | Verifier issues | 工具事件 |
|---|---|---|---:|---:|---:|---:|
| Excel | SUCCEEDED | `outputs/live_sales.xlsx` | 100.0 / PASS | 7/7 | 0 | 3 |
| Word | SUCCEEDED | `outputs/live_memo.docx` | 100.0 / PASS | 4/4 | 0 | 3 |
| PowerPoint | SUCCEEDED | `outputs/live_review.pptx` | 100.0 / PASS | 3/3 | 0 | 7 |

## 逐项证据

### Excel

- Provider：`openai-chat:deepseek-v4-flash`
- Artifact SHA-256：`718a12d666f5833386a9419b94babbf9185905d7b2e3f18a2877cc55162d68dc`（4925 bytes）
- 运行目录：`C:\Users\sy\Desktop\workagent-rsi\worktrees\office-artifact-assessment-merge\results\rsi-live-api-retry-20261011\20261011T070121Z-live-deepseek-excel-afa92e5f`
- 评分：`assessment/score.json`; 结构化问题：`assessment/issues.json`; 模型调用与工具轨迹：`provider_records/`。

### Word

- Provider：`openai-chat:deepseek-v4-flash`
- Artifact SHA-256：`406c86f03c59d6bfcc58663f61a86f61fee176dcb0a8fd3139e612f9ce2cf573`（36643 bytes）
- 运行目录：`C:\Users\sy\Desktop\workagent-rsi\worktrees\office-artifact-assessment-merge\results\rsi-live-api-retry-20261011-word-deepseek-retry\20261011T091008Z-live-deepseek-word-retry-f6380f0c`
- 评分：`assessment/score.json`; 结构化问题：`assessment/issues.json`; 模型调用与工具轨迹：`provider_records/`。

### PowerPoint

- Provider：`openai-chat:deepseek-v4-flash`
- Artifact SHA-256：`f2784a22ee80cb99517ef56e094272ff056e554362faf34f35c4a19dc8ab3e4c`（28333 bytes）
- 运行目录：`C:\Users\sy\Desktop\workagent-rsi\worktrees\office-artifact-assessment-merge\results\rsi-live-api-retry-20261011-ppt-deepseek-retry\20261011T091207Z-live-deepseek-powerpoint-retry-2ea66a47`
- 评分：`assessment/score.json`; 结构化问题：`assessment/issues.json`; 模型调用与工具轨迹：`provider_records/`。

## 429 恢复修复

API 网关会在工具循环的中间请求返回瞬时 HTTP 429。为避免把网关限流计为任务失败，`WorkAgentConfig` 增加 `api_max_retries` 和 `api_retry_delay_seconds`，OpenAI-compatible provider 会对 429 按指数退避重试。Word 与 PowerPoint 的成功运行使用了该路径；原始 429 运行目录完整保留以供审计。

## 范围与下一步

- 当前评估覆盖本轮声明的结构和内容约束。
- 未执行 COM reopen，也未启动真实 RSI candidate patch 外循环；这两项不能从本轮结果推导为已跑通。
- 下一步应将相同 non-Ollama provider 接入 candidate provider，构造非空 develop/regression/hidden/ood splits，再执行真实 RSI 外循环。
