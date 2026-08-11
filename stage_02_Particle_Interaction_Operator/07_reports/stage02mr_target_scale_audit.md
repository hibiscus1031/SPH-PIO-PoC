# Stage 02M-R — Target scale audit

冻结 `a0 = 400 m s^-2`，未修改。10 个 train graphs 的 `target_tilde RMS` 范围为 `4.304607e-04`–`1.573356e-03`；相应 graph-balanced loss 处于约 1e-7–1e-6 数量级。逐图 dimensional target RMS、target_tilde RMS/Linf、9 组 initial/selected prediction RMS、coefficient RMS/saturation 及 family/resolution/support 范围已机器记录。

该尺度与实测微小梯度、高 epsilon/WD dominance 一致；encoder/head 梯度失衡按模块保留于 conditioning JSON。此结论是诊断，不改变 a0、loss 或 checkpoint。
