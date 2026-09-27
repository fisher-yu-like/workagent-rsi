# 正式研究基线

这里保存正式实验开始前的冻结合约、能力清单和基线清单。它们只描述已经检查到的事实，不把当前项目生成的 30 条 pilot 数据当作外部 benchmark。

- `contract.json`：正式研究的 split、评估器、RSI 预算、provider 和结果目录规则。
- `capability_matrix.json`：当前机器上真实可用、不可用和未声明的能力。
- `baseline_manifest.json`：阶段 0 的测试、编译、数据质量和 Git 证据。

阶段 0 的结果是：现有测试 61 项通过；pilot 数据质量检查 14 项通过；Word、Excel、PowerPoint 16.0 COM 可连接；LibreOffice 命令不可用；外部 WorkAgent provider 尚未配置。因此下一阶段先实现显式 Office provider 和能力探测，不宣称已有外部 WorkAgent 结果。
