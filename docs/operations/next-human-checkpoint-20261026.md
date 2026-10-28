# 下一步人工复核

Current update (2026-10-28): see [remaining work](remaining-work-20261028.md). The approved recovery is complete:26 attempts,24 valid decisions,12 full case pairs;567charged seconds/0tools. Natural20 requirements-based follow-up and judging remain pending;both standard interpretations have been clarified. Earlier run descriptions below are historical snapshots.

更新：用户已提交六例复核文件，接收结果为 3 FAIL、3 INCOMPLETE。原始文件和独立回执已保存，六例无需重新提交。随后批准的 judge v2 累计发出 16 次请求，取得 14 个有效判定、6 个完整双通道案例。第 11、16 次出现 HTTP 429，失败项均未重试。以下复核步骤保留作为操作记录。

本轮已完成本地准备，接下来请先复核六个有分歧的标准例。

打开 [六例复核页面](../../project_artifacts/results/hardening-v2/T28-adjudication/20261026/six-case-v1/index.html)。如果编辑器显示 HTML 源码，请在文件管理器中双击该文件，用浏览器打开。

1. 每例先读“原任务说明”。页面已列出原输入、成品文件和实际渲染页。
2. 按“本次重点核对”查看具体内容。Excel 的求和问题需要打开工作簿查看公式；Word 的总数问题需要对照输入明细计算。不要只看成品外观。
3. 自行选择 PASS、FAIL、PARTIAL 或 INCOMPLETE，写一句依据，并勾选本例的核对确认。无法确认时选择 INCOMPLETE，说明原因。页面没有预选标签。
4. 填写姓名或昵称，点击“下载复核 JSON”。文件名为 `office-human-adjudication.json`。在聊天中告诉我实际保存路径即可。

初次 32 条标签会保留。这次已经提供诊断提示，因此下载的是“复核裁定”，不能作为新的独立盲标导入。导出文件使用独立的来源类型，现有盲标接收器会拒绝把它冒充盲标。完成六例复核也不代表其余自然成品已获得可靠人工真值。

## 本轮已完成的准备

judge v2 的语义通道负责输入文字、明细、公式和结果，以及文本抽取能证明的逻辑位置。实际可见性、遮挡和空间位置由视觉通道负责。视觉请求现在包含原任务的具体要求和允许的替代方案。任务标准不清时仍须保留 NEEDS_REVIEW。

两个通道都是必需检查。任一必需检查返回 FAIL 或 PARTIAL，汇总为未通过；其余情况下，只要有缺失或 NEEDS_REVIEW，汇总仍为 INCOMPLETE。两项 PASS 仅表示声明的检查范围通过，不自动授予完整质量资格。

活动请求清单为 `project_artifacts/results/hardening-v2/T28-judge-pilot/20261026/prepared-v2-final/pilot-manifest.json`。它绑定全部输入、成品和渲染页的哈希。旧版本的批准回执不能启动新清单。原始审阅包及 v1 试运行记录保持不变。

72 个 T31 任务已按原任务文本拆成 405 个草案单元，每段保留原文和位置。它们是待审阅的文本单元，不等同于 405 个独立、完整的任务要求。85 段提出语义检查方案，34 段提出视觉检查方案，286 段明确保留能力或规格缺口。所有 72 份草案均为 reviewed=false、SPEC_INCOMPLETE，未创建人工审阅签名。

主要缺口包括 Excel 的数值重算、精确修改范围和保留区域，Word 的批注、页眉页脚、脚注、修订及格式保留，PPT 的可编辑对象检查和输入参考图与成品的联合比较。简单的文件可读或单页检查不能代替这些要求。草案位于 `project_artifacts/results/hardening-v2/T31-spec-preparation/20261026/drafts-v1/`。

## 本轮模型请求及恢复条件

因为请求内容和汇总规则已经改变，v2 需要对 12 个标准例重新执行完整的 24 次语义／视觉请求，不能沿用旧版 5 个有效判定。准备好的新预算提案为 gpt-6.1-sol、最多 24 次请求、0 次工具调用、累计 1200 秒、每次最多 120 秒，不自动重试或扩额。4096 输出 token 仍是提示要求，CLI 没有服务端硬上限，实际用量需要记录。

准备阶段的预算提案为 allow_live_calls=false、approved_by_user=false。用户随后明确批准该清单，实际批准记录位于 `project_artifacts/results/hardening-v2/T28-judge-pilot/20261026/approved-v2/`，没有复用 v1 授权。v2 实际使用 16 次请求、0 次工具，模型请求累计约 286.15 秒，账本保守记为 295 秒；未运行服务器作业。第一次停止后显式继续了尚未发送的请求，共用原清单、模型身份、批准策略和计数器；没有重新发送失败项。

6 个完整案例中，正常 Excel、Word、PPT 均为声明范围 PASS；遮挡总计的 PPT 和求和范围漏一行的 Excel 为 FAIL；要求含糊的 PPT 为 INCOMPLETE。它们与受控材料参考判断一致，但这只是相关开发标准例，不能称为通用准确率。其余案例没有被补成通过。

还缺 10 个有效通道判定，包括失败的 2 次和未发出的 8 次。若下一次均成功，v2 累计也至少需要 26 次尝试，比原批准上限 24 次多 2 次。尚未发送的 8 次仍在原批准范围内；失败项重试、增加总次数则需要另外明确批准。当前因再次出现 429 停止继续发送，并未自动重试或扩额。已保存同版 14 个有效结果和全部缺失请求清单。包含失败项重试的完整恢复计划仍未批准，不会自动执行。

20 份自然成品不在本轮模型授权中。按现有页面、每次最多 8 张图片计算，至少涉及 20 次语义检查和 30 个已有页面的视觉批次；此外还有 2 例渲染缺口以及尚未确定的文本分片和一致性检查。这是准备工作的下界，不是可直接批准的完整调用预算。

本轮采用相关模块的定向测试，没有重复此前的 Windows 全量测试和服务器 Linux 测试。最终结果和哈希索引见 `project_artifacts/formal_study/hardening_t28_t31_preparation.json`。
