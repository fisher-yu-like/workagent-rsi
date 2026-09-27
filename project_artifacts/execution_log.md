# WorkAgent-RSI 阶段执行日志

> 这份日志用人类易读的语言记录自动执行过程。每次更新保留已完成事项、实际证据、阻塞和下一步；未执行内容不会写成已完成。

## 当前状态

- 总体状态：执行中
- 当前阶段：阶段 2：Office 文件级自动评估器
- 当前任务：先写格式、结构、公式、OOXML、几何检查的失败测试，再实现 evaluator v2
- 自动批准：已收到，后续按计划自动推进；阶段失败时停止并记录原因
- 结果根目录：`project_artifacts/results/`
- 计划文件：[正式研究执行方案](docs/superpowers/plans/2026-09-27-formal-rsi-execution-roadmap.md)

## 2026-09-27：阶段 0 开始

### 已完成

- 已读取并复核正式执行方案。
- 已确认当前工作分支为 `codex/closed-loop-rsi`，本次继续在该隔离分支工作。
- 已确认不删除历史结果，不改变普通单轮“正常任务直接运行”的行为。

### 已完成

- 阶段 0 已通过并提交为 `653066a`。
- 阶段 1 provider 实现已提交为 `3de1ecd3c3ce28f3e6f0ea50b811bb6ce58fd04a`。
- 新增 `office_capabilities.py`：记录 COM、LibreOffice、本地 Python provider 和外部 WorkAgent 状态。
- 新增 `ComOfficeAdapter`、`UnavailableOfficeAdapter`、显式 provider CLI 选择和 `UNAVAILABLE` 状态。
- 25 条公开任务通过 clean commit 的 COM provider qualification：成功 25、失败 0、平均自动分数 1.0，覆盖 Excel/Word/PowerPoint。
- 真实 COM 重开后的 automation 进程数量为 0；资源泄漏回归测试通过。
- 两次中断 invocation 没有被覆盖，原因和修复写入 `formal_study/stage1_manifest.json`。
- 阶段 1 Gate：通过。

### 正在进行

- 为三类 Office 文件写 evaluator v2 的红测试。
- 设计只读、可 hash、与 candidate workspace 解耦的结构化检查报告。

### 已完成

- `py -3.12 -m pytest -q --basetemp="$env:TEMP\\workagent-rsi-stage0"`：`61 passed in 12.39s`。
- `py -3.12 -m compileall -q src tests project_artifacts/phase3_experiments/scripts`：退出码 0。
- `py -3.12 project_artifacts/phase3_experiments/data/quality_check.py`：14 项检查全部通过，任务 30 条，公开 25 条，保护 5 条。
- Python 3.12.10、pydantic 2.13.4、pytest 9.1.1、openpyxl 3.1.5、python-docx 1.2.0、python-pptx 1.0.2、Codex CLI 0.157.1、Ollama 0.34.4 和 `qwen2.5:7b` 已记录。
- Word、Excel、PowerPoint COM 均可连接，版本均为 16.0；LibreOffice/soffice 命令不可用；外部 WorkAgent provider 未配置。
- 已写入 `formal_study/contract.json`、`capability_matrix.json`、`baseline_manifest.json` 和说明文件。
- 阶段 0 Gate：通过。当前 pilot 仍明确标为 qualification/mechanism evidence，不作为外部 benchmark 或正式主结果。

### 尚未完成

- evaluator v2 尚未实现。
- Excel 公式/结构、Word OOXML/分页、PPT 几何/溢出和自动渲染检查尚未加入正式评分。

### 下一步

完成阶段 2 后写入真实结果，并继续阶段 3；若 evaluator hash 漂移、hidden 数据泄漏或不可用视觉通道被转换成分数，则停止并记录阻塞。
