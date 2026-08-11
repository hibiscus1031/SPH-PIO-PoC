# Stage 02M-R — Optimization conditioning

18 个 initialization/selected 点均完成 zero-step backward，逐模块记录 data gradient、WD、Adam m/v、sqrt(v)、epsilon/WD/near-zero fractions、effective update 与 clipping；参数 hash 全部不变：**True**。

Selected、multiplier=1 的参数加权历史 epsilon-dominated fraction 为 `0.997101`，WD-dominated fraction 为 `0.928291`，梯度范数中位数 `6.495e-07`。这支持尺度相关的 Adam/WD 条件化不良。

将同一 loss 仅用于 backward 放大到 1e3/1e6 后，prospective epsilon-dominated fraction 从 `0.997040` 降至 `0.697048` / `0.160234`，WD-dominated fraction从 `0.928291` 降至 `0.367612` / `0.078611`。但 effective-update direction cosine 中位数仅 `0.456` / `0.234`，不满足方向稳定条件，故严格标签为 `LOSS_SCALE_DIAGNOSTIC_CONDITIONING_SENSITIVE_BUT_DIRECTION_UNSTABLE`，不据此授权协议变更。
