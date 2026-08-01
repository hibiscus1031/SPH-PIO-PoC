# Stage 01D-R3 最终报告

## 1. R2 冻结

R2 运行前提交为 `084c702c6eab16b6983078494c01627fd2d8cfbe`，最终证据提交为 `39ae3dc1f88f4468d2a423cfad8c952a0a4da8d3`；annotated tag `stage-01dr2-attribution-unresolved-cutoff-topology` target 为 `39ae3dc1f88f4468d2a423cfad8c952a0a4da8d3`。R2 的 `ATTRIBUTION_UNRESOLVED` 保持不变。

## 2. H/dx=5 的截断壳层退化

q=5 由 12 个整数偏移构成，共 `12288` 条
directed cutoff-shell edges；初始最小 `|r/H-1|` 为
`0.000e+00`，cutoff 与离散壳层重合。

## 3. C1–C3 edge 切换来源

R3 replay 精确复现 `[82940, 82942, 82944]`，与 C1–C3 全部采样行一致；
`4` 个具体 edge keys 全在 q=5 且 r≈H。该现象是
截断壳层 inclusion 切换，不是物理粒子迁移。

| edge key | row | col | offset | shell | actions | min |r/H−1| |
|---|---|---|---|---|---|---|
| 11435 | 11 | 171 | (-5,0) | 5.0 | removed | 3.997e-15 |
| 16560 | 16 | 176 | (-5,0) | 5.0 | removed | 3.997e-15 |
| 175115 | 171 | 11 | (5,0) | 5.0 | removed | 4.219e-15 |
| 180240 | 176 | 16 | (5,0) | 5.0 | removed | 4.219e-15 |

## 4. Control F

| run | steps | edge values | edge IDs | tensor Δ | unknown Δ | old bytes | age-2 | margin | PASS |
|---|---|---|---|---|---|---|---|---|---|
| stage01dr3_f_r1 | 2000 | 1 | 1 | 0 | 0 | 0 | 15 | 0 | False |
| stage01dr3_f_r2 | 2000 | 1 | 1 | 0 | 0 | 0 | 15 | 0 | False |
| stage01dr3_f_r3 | 2000 | 1 | 1 | 0 | 0 | 0 | 15 | 0 | False |

## 5. Control M

`q_next=sqrt(26)`，冻结诊断 ratio=`5.049509756796392`；正常重建结果：

| run | steps | edge values | edge IDs | tensor Δ | unknown Δ | old bytes | age-2 | margin | PASS |
|---|---|---|---|---|---|---|---|---|---|
| stage01dr3_m_r1 | 2000 | 1 | 1 | 0 | 0 | 0 | 0 | 0.0495097567963283 | True |
| stage01dr3_m_r2 | 2000 | 1 | 1 | 0 | 0 | 0 | 0 | 0.0495097567963283 | True |
| stage01dr3_m_r3 | 2000 | 1 | 1 | 0 | 0 | 0 | 0 | 0.0495097567963283 | True |

## 6. Old-survivor、unknown 与 same-slot

六个 F/M run 的 live tensor count Δ、unknown bytes Δ、old-survivor bytes、
same-slot multi-generation 与明确 referrer chain 均为零。M 的 age-2 weakrefs
为零；F 三次均为 `15`。这些 F 引用映射到当前固定拓扑 storage，故
old-survivor 仍为零，但不满足预登记的 age-2=0 门槛。

## 7. R2 D 模型身份复核

四个源文件 SHA-256 与预登记值一致；没有重新拟合模型。重新读取结果为：

| run | β_edge | β_step | β_step CI | γ_step | γ_step CI |
|---|---|---|---|---|---|
| stage01dr2_d_r1 | 48 | 1.552e-12 | [-5.311e-12, 6.734e-12] | 0.000e+00 | [0.000e+00, 0.000e+00] |
| stage01dr2_d_r2 | 48 | 1.552e-12 | [-7.461e-12, 6.758e-12] | 0.000e+00 | [0.000e+00, 0.000e+00] |
| stage01dr2_d_r3 | 48 | 1.552e-12 | [-5.461e-12, 4.750e-12] | 0.000e+00 | [0.000e+00, 0.000e+00] |
| stage01dr2_d_confirm_2000 | 48 | 1.276e-12 | [-2.441e-12, 2.645e-12] | 0.000e+00 | [0.000e+00, 0.000e+00] |

四个 run 均保持 β_edge=48 B/edge，β_step/γ_step 的 95% CI 包含零，且满足
4096/1024 B/step 上限；D old-survivor 仍为零。

## 8. 数值回归

R2 四个 D run 的 step 0–4 共 20/20 行仍为 finite、bitwise equal，最大绝对差为 0。
F/M 六个 2000-step 状态全部有限；campaign 的 `7` 个
子进程全部回收=`True`。

## 9. 唯一 R3 状态

唯一状态为 **`R3_CONFIRMATION_UNRESOLVED`**。

初始自动分析曾把任意 T2 失败映射为 `R3_TOPOLOGY_CONTROL_FAIL`；该映射与
预登记释义“拓扑不能维持固定”不一致，因为六次运行的 edge count 和 identity
均恒定。分类映射修正后，T2 仍为 False、原始证据不变，状态按“证据仍不足”归为
`R3_CONFIRMATION_UNRESOLVED`。修正记录见
`results/classification_correction.json`。

| gate | name | passed | observed | required |
|---|---|---|---|---|
| T1 | cutoff_shell_diagnosis | True | [82940,82942,82944] | q=5 cutoff switches explain 82940/82942/82944 |
| T2 | frozen_topology_control | False | 0/3 | 3/3 |
| T3 | support_margin_control | True | 3/3 | 3/3 |
| T4 | r2_dynamic_evidence_identity | True | 7/7 | 7/7 |
| T5 | numerical_and_provenance | True | 7/7 reclaimed=True | 7/7, finite, identity complete |
| STATUS | unique_r3_status | True | R3_CONFIRMATION_UNRESOLVED | ["R3_WORKING_SET_ATTRIBUTION_CONFIRMED","R3_TOPOLOGY_CONTROL_FAIL","R3_RETENTION_SIGNAL_DETECTED","R3_CONFIRMATION_UNRESOLVED"] |

## 10. Stage 01D2 申请资格

当前结论：**不具备申请 Stage 01D2 新协议的资格**。本阶段没有设计或运行 Stage 01D2。

## 11. 历史状态保持

Stage 01D 仍为 **`V2_FAIL`**；Stage 01D-R 仍为
**`RESOURCE_FAIL_LINEAR_GROWTH`**；Stage 01D-R2 仍为
**`ATTRIBUTION_UNRESOLVED`**。R3 不追溯改写这些状态。

## 12. V3 与 Stage 02

**V3 未开始，Stage 02 未开始。** 未运行正式 V2 时间/空间收敛，未训练神经网络，
未生成学习标签；Control M 的诊断 H/dx 未转为正式参数。

## 证据索引

| path | SHA-256 | bytes |
|---|---|---|
| `06_experiments/stage_01dr3_topology_confirmation/configs/preregistered_topology_confirmation.yml` | 44431531be95a3acbb39f49d571f5995973a154c44b717a2928fabdf9f8c583a | 4168 |
| `06_experiments/stage_01dr3_topology_confirmation/results/cutoff_shell_audit_summary.json` | 01581466a6bb5aa07244ad9c247e6e4e486977e5e93c1bf5626152a449d53003 | 1092 |
| `06_experiments/stage_01dr3_topology_confirmation/results/cutoff_switch_edges.csv` | aaa3576fc6affa34fa0e40f0d2f862636a1951fa71c36a28b3afb3f50c62a9cf | 75655 |
| `06_experiments/stage_01dr3_topology_confirmation/results/campaign_summary.json` | d99710ad2cf0fa8d17cf2c55b4f3d69dfaab602d1314bf2a27c955df5494115d | 318 |
| `06_experiments/stage_01dr3_topology_confirmation/results/control_summary.csv` | 487ed8cbd1193a8424f49d69c0086b2e69de7e99e04c5bd045d270b0424d8eef | 1087 |
| `06_experiments/stage_01dr3_topology_confirmation/results/r2_evidence_identity.csv` | cb81dd7705b39d5c668dc78ca2df7d53d011df0794c3032bfba8f23b96500772 | 836 |
| `06_experiments/stage_01dr3_topology_confirmation/results/r3_gate_evidence.csv` | a2d8b510363ec92a2145e3a42b0cc4e7ac2a120ee72c4276317c3915fb9c5b74 | 538 |
| `06_experiments/stage_01dr3_topology_confirmation/results/analysis_summary.json` | 9f63127d91e020634f74be876fb09271debecafbef8e5f4a48757ab4c21316e4 | 763 |
| `06_experiments/stage_01dr3_topology_confirmation/results/classification_correction.json` | ee329c313e956d538d0725218c793d4a4bd7f2b0369347c12e6317a2e1871744 | 977 |
| `06_experiments/stage_01dr3_topology_confirmation/results/stage01dr3_status.txt` | adb879f5b9099c7ff59f7862e5da4f4782cbd6d0fc565dfb74414273902610bb | 27 |
