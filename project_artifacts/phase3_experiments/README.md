# Phase 3 实验资料

这里保存数据、实验脚本和历史研究证据。日常单轮运行请使用 `workagent_rsi.Harness`；新的结果默认写入 `project_artifacts/results/`。

## 目录说明

- `data/`：项目生成的 30 个 pilot 任务和数据质量记录。
- `provider/`：候选输出的结构约束和提示词。
- `scripts/`：资格检查和 E01-E12 研究实验入口。
- `results/`：历史运行结果，保留用于追溯。

新的资格运行脚本会写入：

```text
project_artifacts/results/qualification/mock/
project_artifacts/results/qualification/office/
project_artifacts/results/experiments/e01_e12/
```

## 运行边界

普通单轮 Pipeline 从正常任务开始，直接生成并检查文件。E01-E12 是研究实验，包含用于测试安全门禁的专门案例；它们不是普通运行的默认流程。

当前 pilot 只用于验证工程闭环，不能表示外部 WorkAgent 的性能，也不是正式主研究结果。E07 使用自动文件评估和自动文本判断，没有人工标注。

## 外部数据与正式入口

`data/external/` 在来源许可、checksum、文件级来源和泄漏检查完成前只保存
metadata。运行 metadata 门禁：

```powershell
py -3.12 project_artifacts/phase3_experiments/scripts/quality_check_external.py
```

正式矩阵有两个明确模式：

```powershell
py -3.12 project_artifacts/phase3_experiments/scripts/run_formal.py --mode pilot --provider deterministic --experiments E01
py -3.12 project_artifacts/phase3_experiments/scripts/run_formal.py --mode formal --provider codex
```

`pilot` 只证明本地工程闭环；`formal` 会在创建结果目录前检查外部数据门禁，
当前因数据尚未获准而拒绝执行。所有输出仍统一放在 `project_artifacts/results/`。
