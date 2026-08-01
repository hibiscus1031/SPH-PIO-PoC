# Stage 01D-R5 最终报告

## 1. R4 冻结

R4 预注册提交为 `32bc4682f4f93eebce831a97f43971f57f087b55`，最终证据提交为 `a3064fe6912657e21f1b842dd8dcbc2f062e82bf`；annotated tag `stage-01dr4-retention-redetected-gc-delayed` target 为 `a3064fe6912657e21f1b842dd8dcbc2f062e82bf`。R4 的 `R4_RETENTION_REDETECTED` 保持不变。

## 2. Retired 对象类型与语义槽

机器清单包含 `1367` 个 retired instance；槽级汇总如下：

| semantic slot | instances | storages | first retired | last alive | owner types | categories |
|---|---|---|---|---|---|---|
| endpoint_neighborhood.displacement | 154 | 110 | 3 | 200 | ["unresolved"] | ["unresolved"] |
| endpoint_neighborhood.distance | 154 | 110 | 3 | 200 | ["unresolved"] | ["unresolved"] |
| endpoint_neighborhood.edge_support | 154 | 115 | 3 | 200 | ["unresolved"] | ["unresolved"] |
| midpoint_neighborhood.displacement | 98 | 67 | 5 | 200 | ["unresolved"] | ["unresolved"] |
| midpoint_neighborhood.distance | 98 | 70 | 5 | 200 | ["unresolved"] | ["unresolved"] |
| midpoint_neighborhood.edge_support | 98 | 73 | 5 | 200 | ["unresolved"] | ["unresolved"] |
| old_state.densities | 88 | 60 | 3 | 200 | ["unresolved"] | ["unresolved"] |
| old_state.positions | 87 | 70 | 3 | 200 | ["unresolved"] | ["unresolved"] |
| old_state.pressures | 88 | 75 | 3 | 200 | ["unresolved"] | ["unresolved"] |
| old_state.velocities | 87 | 69 | 3 | 200 | ["unresolved"] | ["unresolved"] |
| start_stage_neighborhood.displacement | 87 | 68 | 5 | 200 | ["unresolved"] | ["unresolved"] |
| start_stage_neighborhood.distance | 87 | 69 | 5 | 200 | ["unresolved"] | ["unresolved"] |
| start_stage_neighborhood.edge_support | 87 | 71 | 5 | 200 | ["unresolved"] | ["unresolved"] |

## 3. 同槽 9 代的来源

逐项生命周期区间重建得到：

| semantic slot | peak concurrent retired generations | first peak step | last peak step |
|---|---|---|---|
| endpoint_neighborhood.displacement | 13 | 117 | 122 |
| endpoint_neighborhood.distance | 13 | 117 | 122 |
| endpoint_neighborhood.edge_support | 13 | 117 | 122 |
| midpoint_neighborhood.displacement | 7 | 102 | 117 |
| midpoint_neighborhood.distance | 7 | 102 | 117 |
| midpoint_neighborhood.edge_support | 7 | 102 | 117 |
| old_state.densities | 10 | 105 | 106 |
| old_state.positions | 9 | 105 | 106 |
| old_state.pressures | 10 | 105 | 106 |
| old_state.velocities | 9 | 105 | 106 |
| start_stage_neighborhood.displacement | 12 | 116 | 122 |
| start_stage_neighborhood.distance | 12 | 116 | 122 |
| start_stage_neighborhood.edge_support | 12 | 116 | 122 |

在 L1 的 200-step 定位运行中，最大重叠数恰为 9 的槽是
`old_state.positions, old_state.velocities`，二者都在 steps 105–106 达到 9。邻域槽还出现更高峰值，
因此 R4 的聚合峰值 9 不能解释为单一固定 owner；owner/referrer 归属仍为 unresolved。

## 4. GC 前 referrer 图

| representative | nodes | edges | cycle localized | cycle type paths |
|---|---|---|---|---|
| unresolved:endpoint_neighborhood.displacement | 20 | 19 | False | [] |
| unresolved:endpoint_neighborhood.distance | 20 | 19 | False | [] |
| unresolved:endpoint_neighborhood.edge_support | 20 | 19 | False | [] |
| unresolved:midpoint_neighborhood.displacement | 4 | 3 | False | [] |
| unresolved:midpoint_neighborhood.distance | 4 | 3 | False | [] |
| unresolved:midpoint_neighborhood.edge_support | 4 | 3 | False | [] |
| unresolved:old_state.densities | 8 | 7 | False | [] |
| unresolved:old_state.positions | 8 | 7 | False | [] |
| unresolved:old_state.pressures | 8 | 7 | False | [] |
| unresolved:old_state.velocities | 8 | 7 | False | [] |
| unresolved:start_stage_neighborhood.displacement | 16 | 15 | False | [] |
| unresolved:start_stage_neighborhood.distance | 16 | 15 | False | [] |
| unresolved:start_stage_neighborhood.edge_support | 7 | 6 | False | [] |

明确闭环已定位=`False`；没有类型闭环路径时不作闭环声明。

## 5. Default/disabled/periodic GC 对照

| run | mode | max retired | max bytes | same-slot | max gen/slot | first peak | second peak | slope | R² | natural GC | post-GC max | periodic zero | GC wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stage01dr5_g1_r1 | G1 | 69 | 34865152 | 13 | 10 | 57 | 69 | 0.01066 | 0.233 | 581 | 67 | 0.025 | 0.000 |
| stage01dr5_g2_r1 | G2 | 19993 | 10712432640 | 13 | 1999 | 9993 | 19993 | 10 | 1.000 | 0 | -1 | 0.000 | 0.000 |
| stage01dr5_g3_r1 | G3 | 33 | 18710528 | 13 | 6 | 33 | 25 | -0.0004273 | 0.001 | 720 | 25 | 1.000 | 1.888 |
| stage01dr5_g1_r2 | G1 | 64 | 34766848 | 13 | 9 | 61 | 64 | 0.005811 | 0.075 | 579 | 54 | 0.025 | 0.000 |
| stage01dr5_g2_r2 | G2 | 19993 | 10712432640 | 13 | 1999 | 9993 | 19993 | 10 | 1.000 | 0 | -1 | 0.000 | 0.000 |
| stage01dr5_g3_r2 | G3 | 33 | 18710528 | 13 | 6 | 33 | 25 | -0.000601 | 0.003 | 720 | 25 | 1.000 | 1.892 |
| stage01dr5_g1_r3 | G1 | 66 | 37388288 | 13 | 10 | 62 | 66 | 0.007448 | 0.121 | 579 | 66 | 0.013 | 0.000 |
| stage01dr5_g2_r3 | G2 | 19993 | 10712432640 | 13 | 1999 | 9993 | 19993 | 10 | 1.000 | 0 | -1 | 0.000 | 0.000 |
| stage01dr5_g3_r3 | G3 | 33 | 18710528 | 13 | 6 | 33 | 25 | -0.0004456 | 0.002 | 720 | 25 | 1.000 | 1.894 |

G1 总归零观测：

| run | zero observations | first zero step | last zero step | second-half zeros |
|---|---|---|---|---|
| stage01dr5_g1_r1 | 22 | 1 | 219 | 0 |
| stage01dr5_g1_r2 | 10 | 1 | 1400 | 3 |
| stage01dr5_g1_r3 | 15 | 1 | 1438 | 8 |

三次 G1 均出现重复总归零且预登记上包络判据通过；r1 最后一次总归零为 step 219，故不作
“三个重复在全程持续归零”的扩大表述。G2 三次均以约 10 storage/step、R²≈1 线性增长；
G3 的 25-step checkpoint 归零率均为 1，但只作为机制诊断，不作为修复。

## 6. Instrumentation isolation

| run | mode | components | max retired | same-slot | RSS slope | current tensor Δ | external tensor Δ | finite |
|---|---|---|---|---|---|---|---|---|
| stage01dr5_i0_r1 | I0 | [] | -1 | -1 | 7.44e+04 | 0 | 36028416 | True |
| stage01dr5_i1_r1 | I1 | ["weakref_tracker"] | 103 | 13 | 1.26e+05 | 0 | 0 | True |
| stage01dr5_i2_r1 | I2 | ["semantic_ledger"] | -1 | -1 | 4.898e+04 | 0 | 0 | True |
| stage01dr5_i3_r1 | I3 | ["observer_callback"] | -1 | -1 | 9.436e+04 | 0 | 0 | True |
| stage01dr5_i4_r1 | I4 | ["observer_callback","semantic_ledger","weakref_tracker"] | 63 | 13 | 8.413e+04 | 0 | 0 | True |
| stage01dr5_i0_r2 | I0 | [] | -1 | -1 | 1.118e+05 | 0 | 33259520 | True |
| stage01dr5_i1_r2 | I1 | ["weakref_tracker"] | 95 | 13 | 9.905e+04 | 0 | 0 | True |
| stage01dr5_i2_r2 | I2 | ["semantic_ledger"] | -1 | -1 | 3.751e+04 | 0 | 0 | True |
| stage01dr5_i3_r2 | I3 | ["observer_callback"] | -1 | -1 | 1.013e+05 | 0 | 0 | True |
| stage01dr5_i4_r2 | I4 | ["observer_callback","semantic_ledger","weakref_tracker"] | 55 | 13 | 1.009e+05 | 0 | 0 | True |
| stage01dr5_i0_r3 | I0 | [] | -1 | -1 | 8.306e+04 | 0 | 36028416 | True |
| stage01dr5_i1_r3 | I1 | ["weakref_tracker"] | 85 | 13 | 1.037e+05 | 0 | 0 | True |
| stage01dr5_i2_r3 | I2 | ["semantic_ledger"] | -1 | -1 | 6.79e+04 | 0 | 0 | True |
| stage01dr5_i3_r3 | I3 | ["observer_callback"] | -1 | -1 | 1.5e+05 | 0 | 0 | True |
| stage01dr5_i4_r3 | I4 | ["observer_callback","semantic_ledger","weakref_tracker"] | 58 | 13 | 9.815e+04 | 0 | 0 | True |

## 7. 明确循环或持有链

explicit cycle localized=`False`；instrumentation isolated=
`False`。结论仅采用类型图和隔离曲线实际支持的范围。

## 8. 修复及 before/after

未发现满足修复授权条件的明确项目侧持有关系，因此没有修改 solver 或诊断源码，也没有运行修复后 F/M/D campaign。 周期 GC 未被冒充为代码修复。

## 9. 数值回归

25 个独立 worker（1 个 L1、9 个 GC 对照、15 个 isolation）的 step 0–4 哈希回归通过 `25/25`，全部状态有限；
campaign 进程回收=`True`。未修改物理或 RK2。

## 10. 唯一 R5 状态

唯一状态为 **`R5_BOUNDED_GC_DELAY_CONFIRMED`**。

| gate | name | passed | observed | required |
|---|---|---|---|---|
| R1 | retired_object_inventory | True | 1367 | >0 itemized instances |
| R2 | pre_gc_referrer_graph | True | graphs=13 cycles=False | representative type graphs depth<=4 |
| R3 | gc_schedule_contrast | True | G1bounded=True G2linear=True G3zero=True | bounded/linear/zero |
| R4 | instrumentation_isolation | False | I0stable=False trackerSignal=True | solver-only current storage bounded |
| R5 | numerical_and_provenance | True | workers=25/25 numeric=25/25 | 25/25 reclaimed and hashes equal |
| STATUS | unique_r5_status | True | R5_BOUNDED_GC_DELAY_CONFIRMED | ["R5_INSTRUMENTATION_RETENTION_IDENTIFIED_AND_REMOVED","R5_SOLVER_CYCLE_IDENTIFIED_AND_FIXED","R5_BOUNDED_GC_DELAY_CONFIRMED","R5_UNBOUNDED_RETENTION_CONFIRMED","R5_ATTRIBUTION_UNRESOLVED"] |

## 11. Stage 01D2 / 额外资源审计资格

当前结论：**仅具备申请一次额外资源政策审计的资格，不具备 Stage 01D2 申请资格**。没有建立或运行 Stage 01D2。

## 12. 历史状态

Stage 01D=`V2_FAIL`；Stage 01D-R=`RESOURCE_FAIL_LINEAR_GROWTH`；
Stage 01D-R2=`ATTRIBUTION_UNRESOLVED`；Stage 01D-R3=`R3_CONFIRMATION_UNRESOLVED`；
Stage 01D-R4=`R4_RETENTION_REDETECTED`。全部保持不变。

## 13. V3 与 Stage 02

**V3 未开始，Stage 02 未开始。** 未运行正式 V2 收敛或训练神经网络。

## 证据索引

| path | SHA-256 | bytes |
|---|---|---|
| `06_experiments/stage_01dr5_gc_cycle_localization/configs/preregistered_gc_cycle_localization.yml` | 52626240f728ebc5490905e906b0ef50fd5cbc459280bea6d587ff54530ee815 | 3406 |
| `06_experiments/stage_01dr5_gc_cycle_localization/results/campaign_summary.json` | 9f3a7a41ab3b2152f9f587391bc5fa6e1a47a42af050bdd35301722b2989e75a | 321 |
| `06_experiments/stage_01dr5_gc_cycle_localization/results/retired_object_instances.csv` | b7b8b75bbdd11b4d81123008e29e7915be7ffd98de4535cd0d2859430eb4e1c0 | 244431 |
| `06_experiments/stage_01dr5_gc_cycle_localization/results/retired_slot_summary.csv` | 207a48abc25995fe5220a66bf5778929842e7c1bf21a94f6ccd98a58b6e6977b | 1174 |
| `06_experiments/stage_01dr5_gc_cycle_localization/results/referrer_graph_summary.json` | 00b43bc722fb288efc93661687f5efcee71cef33a253ea2377bd201cf9d6356d | 53231 |
| `06_experiments/stage_01dr5_gc_cycle_localization/results/gc_mode_summary.csv` | 4b9f36d36c300112753cd4745fea266510afb1500df3294997c4b01c4349d178 | 1854 |
| `06_experiments/stage_01dr5_gc_cycle_localization/results/instrumentation_isolation_summary.csv` | 2eadb0cdfa15f734ca7f61edcf5da65741ae78fb82bda2c8b2f7b9b8415f6582 | 1761 |
| `06_experiments/stage_01dr5_gc_cycle_localization/results/numerical_regression_summary.csv` | 8c8ce2c07313519c0a089e5f337b335e4212330e78af7ca7264dda62517e0f62 | 634 |
| `06_experiments/stage_01dr5_gc_cycle_localization/results/r5_gate_evidence.csv` | 355867770ad729df7834fcb937cdad6beb81a08ba9622484055d62cea651a12e | 734 |
| `06_experiments/stage_01dr5_gc_cycle_localization/results/analysis_summary.json` | 795a9b1f435163145e4d984d52648a37daebaaa124f669914bbb370356e9d3af | 872 |
| `06_experiments/stage_01dr5_gc_cycle_localization/results/stage01dr5_status.txt` | 2d69c898fc0d42618b605d2bcf4a47d39715e981336e15313a586319aee3b3f7 | 30 |
