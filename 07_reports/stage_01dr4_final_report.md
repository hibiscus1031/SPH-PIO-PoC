# Stage 01D-R4 最终报告

## 1. R3 冻结

R3 预注册提交为 `2c8c3f377b53315c2c7cb378ec4054b89b96a793`，最终证据提交为 `12bc7e4e56539cd6f14db12f4c9ee6cbe10b3f99`；annotated tag `stage-01dr3-confirmation-unresolved-weakref-semantics` target 为 `12bc7e4e56539cd6f14db12f4c9ee6cbe10b3f99`。R3 的 `R3_CONFIRMATION_UNRESOLVED` 保持不变。

## 2. 旧 age-2 门槛为何失败

R3 Control F 的 raw age-2 count 为 15。旧门槛要求 age-2=0，因此 T2 严格失败；
该旧规则和 R3 状态均未修改。R4 单独检查这些 storage 是否已退休。

## 3. Current persistent 与 retired reference

current persistent 仍属于 solver-readable current working set；retired reference 已被
同语义新对象替换且不再属于当前工作集。只有 retired old-survivor 或同槽 retired
多代共存属于 retention signal。

## 4. 15 个 Control F weakrefs 的身份

canonical F1 的 15/15 均为 current persistent、0/15 retired：

| slot | object id | storage key | created | first | last | fixed edge | current | retired | different generation | referrer types |
|---|---|---|---|---|---|---|---|---|---|---|
| endpoint_neighborhood.col | 4437737712 | cpu:5639176192:663552 | 0 | 198 | 200 | True | True | False | False | ["FrozenReciprocalTopology","PeriodicNeighborhood"] |
| endpoint_neighborhood.domain_max | 4437673456 | cpu:5266941248:16 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| endpoint_neighborhood.domain_min | 4437674016 | cpu:5266317184:16 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| endpoint_neighborhood.particle_support | 4437549824 | cpu:4472066560:8192 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| endpoint_neighborhood.row | 4437738752 | cpu:4566351872:663552 | 0 | 198 | 200 | True | True | False | False | ["FrozenReciprocalTopology","PeriodicNeighborhood"] |
| midpoint_neighborhood.col | 4437737712 | cpu:5639176192:663552 | 0 | 198 | 200 | True | True | False | False | ["FrozenReciprocalTopology","PeriodicNeighborhood"] |
| midpoint_neighborhood.domain_max | 4437673456 | cpu:5266941248:16 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| midpoint_neighborhood.domain_min | 4437674016 | cpu:5266317184:16 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| midpoint_neighborhood.particle_support | 4437549824 | cpu:4472066560:8192 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| midpoint_neighborhood.row | 4437738752 | cpu:4566351872:663552 | 0 | 198 | 200 | True | True | False | False | ["FrozenReciprocalTopology","PeriodicNeighborhood"] |
| start_stage_neighborhood.col | 4437737712 | cpu:5639176192:663552 | 0 | 198 | 200 | True | True | False | False | ["FrozenReciprocalTopology","PeriodicNeighborhood"] |
| start_stage_neighborhood.domain_max | 4437673456 | cpu:5266941248:16 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| start_stage_neighborhood.domain_min | 4437674016 | cpu:5266317184:16 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| start_stage_neighborhood.particle_support | 4437549824 | cpu:4472066560:8192 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| start_stage_neighborhood.row | 4437738752 | cpu:4566351872:663552 | 0 | 198 | 200 | True | True | False | False | ["FrozenReciprocalTopology","PeriodicNeighborhood"] |

## 5. 四类诊断夹具

| run | fixture | expected retention | current peak | old peak | same-slot peak | reclaimed | PASS |
|---|---|---|---|---|---|---|---|
| stage01dr4_fixture_a_r1 | A | False | 1 | 0 | 0 | True | True |
| stage01dr4_fixture_b_r1 | B | False | 0 | 0 | 0 | True | True |
| stage01dr4_fixture_c_r1 | C | True | 0 | 99 | 1 | True | True |
| stage01dr4_fixture_d_r1 | D | False | 0 | 0 | 0 | True | True |
| stage01dr4_fixture_a_r2 | A | False | 1 | 0 | 0 | True | True |
| stage01dr4_fixture_b_r2 | B | False | 0 | 0 | 0 | True | True |
| stage01dr4_fixture_c_r2 | C | True | 0 | 99 | 1 | True | True |
| stage01dr4_fixture_d_r2 | D | False | 0 | 0 | 0 | True | True |
| stage01dr4_fixture_a_r3 | A | False | 1 | 0 | 0 | True | True |
| stage01dr4_fixture_b_r3 | B | False | 0 | 0 | 0 | True | True |
| stage01dr4_fixture_c_r3 | C | True | 0 | 99 | 1 | True | True |
| stage01dr4_fixture_d_r3 | D | False | 0 | 0 | 0 | True | True |

Fixture C 的故意 history 同时触发 old-survivor 和 same-slot multigeneration；A、B、D
均无误报，证明分类器既能排除 current persistent，也能检出真实泄漏。

## 6. 短程 F 回归

| run | steps | edges | IDs | age-2 | current | retired | old | same-slot | unknown Δ | referrers | PASS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| stage01dr4_f_r1 | 200 | [82944] | 1 | 15 | 15 | 0 | 12 | 9 | 0 | 0 | False |
| stage01dr4_f_r2 | 200 | [82944] | 1 | 15 | 15 | 0 | 15 | 9 | 0 | 0 | False |
| stage01dr4_f_r3 | 200 | [82944] | 1 | 15 | 15 | 0 | 18 | 9 | 0 | 0 | False |

三个独立子进程均完成 200 steps，edge identity 唯一，状态有限并完全回收。

## 7. Old-survivor 与 same-slot history

目标 step 200 的 15 条 age-2 refs 均为 current，且强制 GC 检查点的 retired count
归零；但 F1–F3 在非 GC accepted steps 的 retired old-survivor 峰值分别为
`[12, 15, 18]`，same-slot multigeneration 峰值为 `[9, 9, 9]`。unknown bytes Δ=0、
明确 referrer chain=0。协议不允许用后续 GC 归零撤销已经观测到的 retired
old-survivor，因此 retention 被重新检出。

## 8. R2/R3 证据复核

六份冻结输入的 SHA-256 与预登记一致，没有重新拟合或回写：

| run | β_edge | β_step CI | γ_step | old evidence |
|---|---|---|---|---|
| stage01dr2_d_r1 | 48 | [-5.311e-12, 6.734e-12] | 0.000e+00 | SHA-verified |
| stage01dr2_d_r2 | 48 | [-7.461e-12, 6.758e-12] | 0.000e+00 | SHA-verified |
| stage01dr2_d_r3 | 48 | [-5.461e-12, 4.750e-12] | 0.000e+00 | SHA-verified |
| stage01dr2_d_confirm_2000 | 48 | [-2.441e-12, 2.645e-12] | 0.000e+00 | SHA-verified |

β_edge=48 B/edge，β_step CI 均包含 0，γ_step=0；R2/R3 old-survivor=0，
Control M 3/3 通过，82940/82942/82944 的 q=5 cutoff 壳层解释保持成立。

## 9. 唯一 R4 状态

唯一状态为 **`R4_RETENTION_REDETECTED`**。

| gate | name | passed | observed | required |
|---|---|---|---|---|
| G1 | fifteen_reference_identity | True | canonical=15/15; all runs current=45/45 | 15/15 current and 0 retired in each run |
| G2 | fixture_validation | True | 12/12 | 12/12 including positive leak detection |
| G3 | short_f_retired_storage | False | 0/3; old peaks=[12, 15, 18] | 3/3 with retired old-survivor=0 and same-slot=0 |
| G4 | frozen_evidence_identity | True | 11/11 | 11/11 |
| G5 | process_and_provenance | True | 15/15 reclaimed=True | 15/15, all reclaimed |
| STATUS | unique_r4_status | True | R4_RETENTION_REDETECTED | ["R4_WEAKREF_GATE_SEMANTICS_CONFIRMED","R4_RETENTION_REDETECTED","R4_GATE_VALIDATION_FAIL","R4_UNRESOLVED"] |

## 10. Stage 01D2 协议申请资格

当前结论：**不具备申请 Stage 01D2 新协议的资格**。该资格仅允许提交下一轮审计、申请设计新协议；
本阶段没有建立、设计或运行 Stage 01D2。

## 11. 历史状态保持

Stage 01D=`V2_FAIL`；Stage 01D-R=`RESOURCE_FAIL_LINEAR_GROWTH`；
Stage 01D-R2=`ATTRIBUTION_UNRESOLVED`；Stage 01D-R3=`R3_CONFIRMATION_UNRESOLVED`。
所有旧状态、报告和机器证据均未修改。

## 12. V3 与 Stage 02

**V3 未开始，Stage 02 未开始。** 未运行正式 V2 时间/空间收敛，未训练神经网络，
未修改 SPH 物理、RK2、支撑规律或第三方源码。

## 证据索引

Campaign 15/15 worker PASS，全部回收=`True`。

| path | SHA-256 | bytes |
|---|---|---|
| `06_experiments/stage_01dr4_weakref_semantics/configs/preregistered_weakref_semantics.yml` | 3e3ee24edd6bf4c20a5b6093f0c0d09fb92e2b5a7b3c0d041d699dc7298e7081 | 3632 |
| `06_experiments/stage_01dr4_weakref_semantics/results/campaign_summary.json` | ba1b709b5ab7a192da23de417c61293f4346126d73ee88f85b26eab02a68fc1f | 321 |
| `06_experiments/stage_01dr4_weakref_semantics/results/fixture_summary.csv` | 4d48fd85d76fc8023ea634af5cc7059d6d0c22d436042efe24e10bda38277f2e | 757 |
| `06_experiments/stage_01dr4_weakref_semantics/results/control_f_semantic_summary.csv` | 7c8113541dc1b0b936ac155968a466482d08b64351a7ba74b56fe50d18804d6c | 489 |
| `06_experiments/stage_01dr4_weakref_semantics/results/fifteen_reference_identity.csv` | ac3797f8949ea30ba835e5ffca8421cbd6387020f9d1c6c3b7e36c86d8cd752e | 3255 |
| `06_experiments/stage_01dr4_weakref_semantics/results/evidence_identity.csv` | 6c470dfbb6b3bc7ae3bf2485bc29f98424d393e341366e782110f748581fb438 | 1260 |
| `06_experiments/stage_01dr4_weakref_semantics/results/r4_gate_evidence.csv` | 1aff19fa145b00f53582b3706d24bea5e9129bccb61cd4e56f792eb45a22a74d | 625 |
| `06_experiments/stage_01dr4_weakref_semantics/results/analysis_summary.json` | 1c766186f5706afd9918400e9a1f723fc9a3eb4501d4798433943bef05d22f4d | 692 |
| `06_experiments/stage_01dr4_weakref_semantics/results/stage01dr4_status.txt` | 737e6a0d9db70184e0cac35dc6cb2e1c445ef0ad42e11601fbfbbc93bef15df3 | 24 |
