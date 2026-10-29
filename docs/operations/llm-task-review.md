# LLM 任务评估协议

任务合理性、产物是否完成、质量分数和问题诊断均由 LLM 给出。代码读取文件、渲染页面、执行计算、调用模型并保存结果，不预先规定某道任务的答案或给模型结果重新判分。

## 两个 loop

内循环保持 skill 不变，用模型报告中的问题修复当前产物，再调用相同评估协议。外循环修改 skill 后，重新执行一批任务，比较各任务的模型评估结果。版本记录、修改权限、预算、统计和回滚属于执行管理，仍由代码实现。

`SharedAssessment` 将原任务、授权输入、成品文本和原生结构、可用的实际渲染页组织为一次任务级请求。`TaskJudgement` 返回任务是否明确可行、总体状态、分数、理由、证据引用和问题列表。`ArtifactEvaluator` 只适配报告格式；`ArtifactVerifier` 只传递模型的问题和建议。没有权重加总、关键项阈值或 PARTIAL 到 FAIL 的转换。

模型未配置、调用失败、数据超出上下文或图片预算时保留工程缺口和空分数。不能使用旧规则代判成功。引用不存在的证据属于响应格式错误，原回复保留；它不能被记录为产物业务错误。多个独立评估由实验层安排，不在任务层用代码投票或平均分。

## 输入与运行

两个 Office 评估技能使用相同输入：

```json
{
  "task": {
    "task_id": "example",
    "domain": "word",
    "instruction": "根据原始文件完成指定修改，并保留其他条款。",
    "input_files": ["source.docx"]
  },
  "artifacts": {"output": "output.docx"}
}
```

```powershell
.venv\Scripts\python.exe skills/office-artifact-evaluator/scripts/evaluate.py request.json --model-config judge.json --output <new-output-directory>
```

`judge.json` 使用现有 `ModelReviewConfig`，例如配置 `provider: api`、明确的模型名、API 地址和凭据环境变量名。默认 provider 为 disabled。调试可以注入 transport 或 CLI runner；测试中的模型替身不证明真实判断准确率。真实调用须使用另行确认的配置和预算，本次代码迁移没有新增付费请求。

任务级 provider 只接受 `repeats: 1`；独立重复由实验层安排。旧配置中的
`cache_enabled`、`semantic_enabled`、`disagreement_tolerance` 和 `max_text_items`
为读取历史配置而保留，不再控制逐项评分、缓存或投票。`visual_enabled` 仍控制
默认渲染器的装配；文本字符数和图片预算仍生效。

读取器不会把关键词、单元格、公式或原生对象数量转成业务 PASS/FAIL。Word 观测包含正文、表格、批注、页眉页脚、脚注和相关 XML；Excel/PPT 的文本、数据和结构复用通用取证工具，重算与原生结构读取工具也保留。归档原文件名随产物引用保存，避免哈希存储路径丢失文件名信息。

渲染仍需要已配置的隔离 Office worker。缺少 renderer 或实际图片时，模型必须看到相应取证限制，不能据文本猜测外观。当前一次任务请求有上下文和图片数量上限，超限时不会静默截断或扩大预算；更长的任务仍需扩大已配置上限或安排更细的读取操作。

## 删除与保留

删除了按任务生成规则的两个 T31 脚本、任务说明绑定配置、销售题专属 oracle，以及 Word/PPT 原生判定、公式判定、授权修改判定和注册表/需求覆盖率准入实现。旧 Office 判分路径、逐项语义/视觉评分汇总与关键词回退也已移除。

保留了通用 XML、结构和位置读取，模型 API/CLI 传输，渲染和重算执行，原始回复、哈希、预算与日志，以及技能修改验证和实验管理。历史 JSON 数据类型和已完成的实验记录继续保留。旧反例清单明确记录退役的规则测试，不把它们标成已通过新模型校准。

两个评估技能、Harness 和真实 WorkAgent 外循环均连接同一协议。旧的 `expected_constraints` 仍可存在于历史任务记录中，但不再编译为验收代码，也不作为隐藏答案发送给模型。旧任务规格调用不能自动转成新协议的模型成功结果。

## 验证范围

本次验证覆盖模型状态/分数原样传递、两种传输序列化、非正文读取、图片与来源绑定、文件变化、内循环修复、跨任务候选比较、隐藏反馈、预算与回滚。结果以本次测试记录为准；没有新真实 judge 批次、服务器执行或新的 benchmark/研究收益声明。
