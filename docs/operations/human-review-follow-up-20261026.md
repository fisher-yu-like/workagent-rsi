# 首轮人工标注的核对说明

已接收用户提供的 `C:/Users/Lenovo/Downloads/office-human-labels.json`。文件包含 32 条标注：29 PASS、2 FAIL、1 PARTIAL。原始文件逐字节保存，没有替换任何标签。用户明确说明这次主要是快速浏览，因此这些记录属于初步人工判断，不能直接当作可靠真值计算 evaluator 的误判率。

## 为什么会看到重复任务

32 例中有 24 种不同的任务说明。5 组说明文字相同，共涉及 13 份成品；32 份成品的文件哈希全部不同。

- 标准例每个领域各有正确、缺陷、等价方案和要求含糊的版本。它们会共享主要任务要求，用于检查审阅者和 evaluator 能否区分细节。这些版本属于相关样本，不能算独立的任务家族。
- 自然 Excel 任务来自 benchmark；不同工作簿会使用相同的通用审计或财务建模说明。输入文件和实际数值不同，需要分别检查。

原页面没有清楚说明这种安排，也没有给任务段落加“任务说明”标题。生成器已补充提示，适用于以后生成的新包。已经审阅的 32 例原包保持不变。

## 最值得核对的六个标准例

下面是受控标准材料及重新运行的固定检查所提供的定位信息，不是新模型 judge 的判定，也不会自动改写人工标签。

| 案例 ID | 首轮标注 | 需要核对的内容 |
|---|---|---|
| `review-070bf88a4446ba8f` | PASS | Excel 的 `Ledger!B6` 为 `=SUM(B2:B3)`，任务要求覆盖三行，应该检查到 `B4`。外观正常容易漏掉这一点。 |
| `review-ccfa7110e2ffbd7e` | PASS | Word 汇总段落写的是 `Total 52`；根据这份输入的明细，固定检查得到的期望是 `Total 51`。 |
| `review-0db11ab1e4e3d5e1` | FAIL | 任务最后一句明确允许在表格末尾加一个 `Total` 汇总行。它不增加原始明细条目，属于允许的替代方案。 |
| `review-6cda065fb91529a5` | PASS | Excel 任务额外要求标记“重要结果”，但没有定义何为重要。单凭成品不能确认全部要求已满足，适合保留为 INCOMPLETE。 |
| `review-3dfbb6e577ab463f` | PASS | Word 同样存在未定义的“重要结果”要求。这里测试的是能否识别标准不清。 |
| `review-01c7eae4091c4f6e` | PASS | PPT 同样存在未定义的“重要结果”要求。成品可以看起来正常，但完整任务验收仍不确定。 |

此外，`review-4a85dc3e1d4675c8` 的标签是 PARTIAL，备注是“暂时没有发现明显问题”。这两者表达的含义不同，适合以后确认是否发现了未完成的具体要求；目前保留原样。

不需要为了纠正这些说明立即重做整包。后续可先核对上述少量案例，再决定自然成品需要抽查哪些内容。若提交修订，请保留第一轮文件，把新的记录作为“复核／裁定”保存。已经看过检查结果后的修订不能重新称为独立盲标。

现在可以直接使用 [六例复核页面](../../project_artifacts/results/hardening-v2/T28-adjudication/20261026/six-case-v1/index.html)。操作步骤见 [下一步人工复核](next-human-checkpoint-20261026.md)。页面没有默认答案，完成后下载独立的 `office-human-adjudication.json`。

## 自然 Excel 的目标检查

另对 10 份自然 Excel 成品进行了重新重算与已固定上游目标检查，未使用人工标签。6 例目标核对未通过，4 例因动态公式或外部工作簿链接等条件无法完整重算，后四例没有被记为失败或零分。

这些结果使用当前 LibreOffice 环境，尚未建立与 benchmark 官方运行环境的一致性，不能称为正式 benchmark 成绩，也不能直接把所有差异归为产物缺陷。例如，一处文字从 `Andarko` 改为 `Anadarko`，严格回归比较拒绝了该变化，但是否属于任务允许的文字更正需要单独核对。数值差异同样保留具体单元格与参考／输出值供检查。

原始目标诊断：`project_artifacts/results/hardening-v2/T28-native-diagnostics/20261026/run-v1/native-checks.json`。本次共执行 19 个服务器重算作业，临时工作区和进程清理检查均通过，没有安装服务器软件或修改镜像。

## 已批准的模型试运行

12 个标准例共准备了 24 次请求，每例分别进行语义和视觉检查。收到本轮预算批准后，实际发出 6 次请求，其中 5 次取得有效判定；第 6 次遇到 HTTP 429 限流，按“不自动重试”的批准条件停止。没有继续发送其余 18 次请求，工具调用为 0。

2 例取得了完整的双通道意见，另 1 例只有语义意见。正常 Excel 例两项均为 PASS。存在黑色遮挡条的 PPT 例，视觉模型指出遮挡并给出 PARTIAL；语义模型指出文本抽取无法验证显示位置，给出 NEEDS_REVIEW。保守汇总保留 INCOMPLETE，不将其升级为整份任务通过。另一 PPT 例也因位置证据不足及视觉请求失败保留 INCOMPLETE。

这批结果尚不足以完成 T28 校准，不能拿来宣布 evaluator 的准确率。已返回请求的可见用量为 81,625 输入 token、3,158 输出 token；失败请求的 token 用量未知。实际请求时间约 128.36 秒，预算账本保守记账 132 秒。4096 输出 token 是提示要求；CLI 没有服务端输出硬上限。

## 证据位置

- 原始提交、标签与接收回执：`project_artifacts/results/hardening-v2/T28-human-intake/20261026/submission-v1/`。
- 重复审计：同目录上一级的 `repetition-audit.json`。
- 标准例差异：`controlled-standard-triage.json`。
- 标准例的固定检查：`fresh-standard-checks.json`，保留最初核对时的评估器身份；当前代码的完整 90 例校准另存于 `project_artifacts/results/hardening-v2/T34-human-release/20261026/calibration/`。
- 首批 12 例 judge 请求与实测：`project_artifacts/results/hardening-v2/T28-judge-pilot/20261026/`，其中 `actual-v1/diagnostic-summary.json` 记录停止原因与实际用量，`human-comparison.json` 保留初步差异及缺少 judge 的分母。

比较代码已区分“人工与 judge 不同”和“evaluator 已被证实误判”。快速、存疑的人工标签会保留描述性一致性统计，但不授予参考标签门禁或完整质量资格。
