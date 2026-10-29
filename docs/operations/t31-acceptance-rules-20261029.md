# T31 验收规则进展（2026-10-29）

> Historical protocol snapshot. On 2026-10-29 the user replaced coded task acceptance with [task-level LLM review](llm-task-review.md). Rule coverage, rule-authoring commands and per-criterion scoring below are historical records, not current run instructions. Native reading, rendering, transport and experiment controls remain where applicable.

当前自动评估阶段已结束：20 例的 92 个通道均有有效结果，累计 111 次请求、6256 秒。汇总为 18 个 FAIL、2 个 INCOMPLETE，含义限于已声明的检查范围，不能据此报告人工准确率或官方 benchmark 分数。

T31 的 72 个任务已生成新的验收计划，保留原有全部 405 条原文单元和输入哈希。**规则尚未全部补齐，T31 也未完成正式验收。**未覆盖项从 262 条降到 140 条，所有计划仍为 `SPEC_INCOMPLETE`，没有生成独立审阅签名。

| 格式 | 本轮增加的能力 | 仍未覆盖的原文单元 |
|---|---|---:|
| Word | 66 条原生包规则，涉及正文、表格、页眉页脚、脚注、批注和修订标记 | 5 |
| PPT | 24 个任务绑定原图，每个视觉批次同时附上原图和成品页 | 48 |
| Excel | 90 处指标行标签定位，记录工作表、单元格、年份标签和现有公式等信息 | 87 |

90 处 Excel 定位是原文件中的标签位置，不代表已经推导出 90 个数值答案。原文单元也不一定是单一要求，复合要求仍需进一步拆解或联合验证。

## 已实现的检查

Word 检查支持跨 run 的精确替换、原位置显式加粗保留、段落文本清单、批注作者和数量、正文批注锚点、指定批注删除并保留其他批注、脚注追加、表格行和值、空段落位置，以及原生修订和文本修订标记清理。它们不能单独证明全部格式保留或法律意见正确。

加粗来自继承样式、同名词有多种格式或无法确定加粗对应位置时，检查返回待审。仅比较加粗次数不足以证明原位置格式保留。

PPT 原图必须属于冻结输入，文件哈希必须匹配。原图占用图片预算，每批判定必须同时引用原图和成品页。原图变化或判定过程中附件变化会拒绝结果；无效结果不能作为 PASS 写入缓存。原生对象数量检查与视觉重建检查仍各自保留。

按任务编写的规则绑定原始说明哈希。说明改变后不能继续套用旧规则。确定性检查已经替代某条语义检查时，会移除被替代的检查，避免重复请求模型。旧规则、失败记录和原文件均保留。

## 尚需补齐

- Excel：明确答案区域、允许修改的区域、独立数值依据和重算条件。“填满所有空白”“彻底修复所有错误”等说明本身不能唯一确定这些范围；不能仅凭空白格带格式就将它视为答案格。
- PPT：建立原图内容与原生对象的对应关系。存在一个文本框、渲染看起来相似，不能证明原图中所有文字均可编辑。48 条复合要求仍未取得完整检查覆盖。
- Word：仍有 5 条原生内容或保留要求未覆盖。批注是否具体且可执行、法律结构是否保持、灰色字段格式等问题，不能仅靠文字出现或数量达标判断。
- 独立准入：需要独立审阅者或已审 benchmark 的验收清单，绑定最终任务和规格哈希。自动生成规则不能代签。这里没有重新要求 T28 人工复核。

关于模糊任务是否暂不纳入正式资格集，已向用户提出范围选择。在收到答复前，材料继续保留，不自行排除或放宽要求。

## 验证

定向回归快照通过 190 项测试；之后的规则映射调整通过 7 项测试，图片判定后哈希复查调整通过 39 项相关测试，最终 Word 格式不确定性修正通过 66 项相关测试。这些集合存在重叠，不能相加作为独立测试数量。没有重复运行整套约 800 项测试，也没有声称完成新的 Linux 或发布资格验收。

72 份规格均通过注册语法检查。通道未启用时，能力预检为 27 份 `PASS`、45 份 `ASSESSMENT_INCOMPLETE`；语法或能力预检通过不等于任务验收通过。

20 份未修改的 Word 原文件作为反例检查时全部返回 FAIL，证明“尚未执行要求的编辑”不会被这些检查接纳。这是检查器验证，不是 agent 基线或修复收益实验。全部输入哈希和 405 条原文位置均已复核。T31 规则准备调用模型 0 次、服务器作业 0 次。

## 文件与复现

- [交付记录](../../project_artifacts/formal_study/hardening_t31_acceptance_rules_20261029.json)
- [140 条剩余缺口及对应原文](../../project_artifacts/formal_study/acceptance_rules/20261029/remaining-gaps.json)
- [72 个任务的摘要和文件哈希](../../project_artifacts/formal_study/acceptance_rules/20261029/report.json)
- 本地详细规则：`project_artifacts/results/hardening-v2/T31-acceptance-rules/20261029/source-bound-final-v4/`。这些从原文件派生的规则留在本地；版本控制保留生成脚本、说明哈希及精简审计记录。

在原始授权输入可用时，可指定一个不存在的新输出目录复现：

```powershell
.venv\Scripts\python.exe project_artifacts/phase3_experiments/scripts/complete_qualification_specs.py --tasks project_artifacts/results/hardening-v2/T31-prepared/20261026/task-bundle.draft.json --output <new-output-directory>
```
