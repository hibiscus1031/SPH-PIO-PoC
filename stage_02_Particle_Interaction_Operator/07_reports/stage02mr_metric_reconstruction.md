# Stage 02M-R — Metric reconstruction

所有 164 个历史 interval checkpoint 均在 train/validation 上重建；test 未重评。每个检查点的 graph/family Q_L2、Q_Linf、cosine、resolution/support、prediction/target RMS 和 zero-correction improvement 均保存在机器记录中。

| run | init train Q | best-train update/Q | selected update/Q | terminal update/Q |
|---|---:|---:|---:|---:|
| K0_seed20261201 | 0.998373 | 300 / 0.993085 | 100 / 0.994009 | 300 / 0.993085 |
| K0_seed20261202 | 1.000602 | 300 / 0.993927 | 40 / 0.994128 | 300 / 0.993927 |
| K0_seed20261203 | 1.000261 | 300 / 0.992885 | 40 / 0.993560 | 300 / 0.992885 |
| K1_seed20261201 | 0.998011 | 300 / 0.991511 | 40 / 0.993502 | 300 / 0.991511 |
| K1_seed20261202 | 1.006766 | 300 / 0.992371 | 20 / 0.995741 | 300 / 0.992371 |
| K1_seed20261203 | 0.998994 | 300 / 0.991059 | 40 / 0.992991 | 300 / 0.991059 |
| K2_seed20261201 | 1.001697 | 240 / 0.965867 | 240 / 0.965867 | 440 / 0.992843 |
| K2_seed20261202 | 0.999113 | 740 / 0.652523 | 540 / 0.905022 | 740 / 0.652523 |
| K2_seed20261203 | 1.001779 | 260 / 0.959224 | 20 / 0.993811 | 300 / 0.992399 |

任一历史检查点达到 train family-balanced `Q_L2 <= 0.25`：**否**。分类：**NEVER_FIT_TRAIN**。
