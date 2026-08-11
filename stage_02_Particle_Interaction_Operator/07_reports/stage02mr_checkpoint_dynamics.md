# Stage 02M-R — Checkpoint dynamics

9 个 run 的完整机器序列和 12 通道图已生成，包括 loss、train/validation Q_L2、LR、gradient norm、clipping、alpha/beta RMS 与 saturation、parameter norm 和 update/parameter ratio。

K0/K1 在 terminal 仍约为 0.991–0.994，表现为持续欠拟合。K2 的 seed 20261202 从 selected 0.905 降至 terminal 0.653，但仍未触及 0.25；另有 seed 出现 selected 后 train/validation 退化，说明 seed instability 与局部 overfit/plateau 存在。所有 run 依冻结 patience 规则 early-stop，但没有 terminal checkpoint 达门，因此 early stopping 与 checkpoint selection 不是主要失败来源。分析没有触发重选。
