# Stage 01F2 freeze and provenance

Stage 01F 预注册提交为 `153c1d274d91640615805cbf02fa4174e11d336b`，最终证据提交为 `f835b059d98c5a417551a9a349b3537b8c4d2b35`，唯一冻结状态为 `MMS_SPECIFICATION_PASS`。Annotated tag `stage-01f-mms-specification-pass` 指向最终证据提交。

冻结清单覆盖 Stage 01F 最终报告、evaluator、预注册配置、随机点、边界邻近点、项尺度、粒子初始化、source injection contract 及 Stage 01E manifest，共 9 项；`stage01f_freeze_audit.json` 中所有 SHA-256、参数、tag target 和状态检查均为 PASS。Stage 01F 原文件未修改。

Stage 01F2 动态实现基线提交为 `e6a8ac2709c3bb6bd214d37f9f5879c01cb32566`；强化的全变量 AD/FD 审计提交为 `908f366ffa415c83a40ea5329f0b8b5f0e4c1845`。配置 SHA-256 为 `d66a5a0db2e4d3c9d668d3e358707b76a192031790f86e5895d661ff235b7f13`。动态任务使用冻结环境 Python 3.12、PyTorch 2.13.0、SciPy 1.18.0、float64 CPU。最终判定以 `stage01f2_evaluation_v2.json` 为准。

证据边界仅为 implementation smoke、code-path verification、deterministic repeat、reference sensitivity 和 balance audit。未形成正式精度资格结论。
