# Stage 01D-R2 最终报告

## 1. Stage 01D-R 冻结

Stage 01D-R 诊断协议提交为 `0d562a4d8ed662c33797b738cd0f7ae9c00c1618`，最终证据提交为 `3f5d2d5033cfadd559cc278c4f828b40bc40d324`。Annotated tag `stage-01dr-resource-fail-live-bytes-gate` target 为 `3f5d2d5033cfadd559cc278c4f828b40bc40d324`。旧状态 `RESOURCE_FAIL_LINEAR_GROWTH` 与 Stage 01D 的 `V2_FAIL` 均未修改。

## 2. Gate G 为什么失败

Stage 01D-R 的 Gate G 在 N16/N32、A/B/C 六个组合中均观察到 3/3 次
live-tensor estimated bytes 正斜率，而 live tensor count、tracemalloc 与 GC tracked
objects 未同步增长。旧协议按预登记规则保守选择 `RESOURCE_FAIL_LINEAR_GROWTH`；R2
不改写该失败，只进一步区分当前工作集尺寸与历史 storage。

## 3. Tensor inventory 自验证

| run | iterations | tensor Δ | storage Δ | fixture tensors | unique storages | PASS |
|---|---|---|---|---|---|---|
| stage01dr2_a_r1 | 1000 | 0 | 0 B (0.000 MB) | 4 | 2 | True |
| stage01dr2_a_r2 | 1000 | 0 | 0 B (0.000 MB) | 4 | 2 | True |
| stage01dr2_a_r3 | 1000 | 0 | 0 B (0.000 MB) | 4 | 2 | True |

Inventory 自保留判定为 **PASS**。

## 4. Semantic storage ledger

所有 project-owned Tensor 均在可观察的创建/返回边界显式注册语义；每条明细包含
object id、data_ptr、nbytes、shape、stride、dtype、device、requires_grad、grad_fn、
view/base storage id 和 semantic slot。多个 view 共享的 storage 只计一次。

## 5. Weakref 生命周期

| run | GC checkpoints | age-2 alive refs | old storage count | old bytes | same-slot history | PASS |
|---|---|---|---|---|---|---|
| stage01dr2_b_r1 | 45 | 0 | 0 | 0 B (0.000 MB) | 0 | True |
| stage01dr2_b_r2 | 45 | 0 | 0 | 0 B (0.000 MB) | 0 | True |
| stage01dr2_b_r3 | 45 | 0 | 0 | 0 B (0.000 MB) | 0 | True |
| stage01dr2_c_r1 | 45 | 0 | 0 | 0 B (0.000 MB) | 0 | True |
| stage01dr2_c_r2 | 45 | 0 | 0 | 0 B (0.000 MB) | 0 | True |
| stage01dr2_c_r3 | 45 | 0 | 0 | 0 B (0.000 MB) | 0 | True |
| stage01dr2_d_r1 | 45 | 0 | 0 | 0 B (0.000 MB) | 0 | True |
| stage01dr2_d_r2 | 45 | 0 | 0 | 0 B (0.000 MB) | 0 | True |
| stage01dr2_d_r3 | 45 | 0 | 0 | 0 B (0.000 MB) | 0 | True |
| stage01dr2_d_confirm_2000 | 85 | 0 | 0 | 0 B (0.000 MB) | 0 | True |

## 6. A/B/C/D 控制

Control A 为 1000 次静态 inventory；B 为冻结 N32 state 的 1000 次 force evaluation；
C 为固定拓扑 zero-flow N32 1000 步；D 为冻结 TGV N32 1000 步、三次重复。
D 三次安全完成后按条件执行一次 2000-step 确认。Campaign 完成
`13` 个独立子进程，全部回收=
`True`。

## 7. Edge count 与 live-byte 相关性

| run | β_edge B/edge | β_step B/step | β_step 95% CI | γ_step B/step | γ_step 95% CI | PASS |
|---|---|---|---|---|---|---|
| stage01dr2_d_r1 | 48.000000 | 0.000000 | [-0.000000, 0.000000] | 0.000000 | [0.000000, 0.000000] | True |
| stage01dr2_d_r2 | 48.000000 | 0.000000 | [-0.000000, 0.000000] | 0.000000 | [0.000000, 0.000000] | True |
| stage01dr2_d_r3 | 48.000000 | 0.000000 | [-0.000000, 0.000000] | 0.000000 | [0.000000, 0.000000] | True |
| stage01dr2_d_confirm_2000 | 48.000000 | 0.000000 | [-0.000000, 0.000000] | 0.000000 | [0.000000, 0.000000] | True |

## 8. Current working set 与 old survivor 分离

| run | edges | edge values | tensor-count Δ | unknown-byte Δ | old-byte Δ | PASS |
|---|---|---|---|---|---|---|
| stage01dr2_b_r1 | 82944 | 1 | 0 | 0 B (0.000 MB) | 0 B (0.000 MB) | True |
| stage01dr2_b_r2 | 82944 | 1 | 0 | 0 B (0.000 MB) | 0 B (0.000 MB) | True |
| stage01dr2_b_r3 | 82944 | 1 | 0 | 0 B (0.000 MB) | 0 B (0.000 MB) | True |
| stage01dr2_c_r1 | 82940 | 3 | 0 | 0 B (0.000 MB) | 0 B (0.000 MB) | False |
| stage01dr2_c_r2 | 82940 | 3 | 0 | 0 B (0.000 MB) | 0 B (0.000 MB) | False |
| stage01dr2_c_r3 | 82940 | 3 | 0 | 0 B (0.000 MB) | 0 B (0.000 MB) | False |

total live bytes 仅用于描述当前进程；真正 retention gate 只使用非当前、age≥2 的
old-survivor storage、相同语义槽的多代并存以及 unknown 的 edge-adjusted step 项。

## 9. 明确持有链

确认的直接持有链数量为
`0`；
`explicit_retention_detected=false`。

## 10. 修复及 before/after

`retention_fix_applied=false`。没有明确持有链时不允许实施修复，因此本阶段没有
before/after 修复曲线，也没有修改 density、EOS、pressure、viscosity、RK2、dt、
H/dx、nu、c_s、layout 或第三方源码。

## 11. 数值回归

| run | rows | finite+bitwise | max abs Δ | PASS |
|---|---|---|---|---|
| stage01dr2_d_r1 | 5 | 5 | 0.0 | True |
| stage01dr2_d_r2 | 5 | 5 | 0.0 | True |
| stage01dr2_d_r3 | 5 | 5 | 0.0 | True |
| stage01dr2_d_confirm_2000 | 5 | 5 | 0.0 | True |

冻结 N32 step 0–4 的 positions、velocities、densities、pressures 使用 float64 bitwise
比较；numerical gate 为 **PASS**。

## 12. 唯一归因状态

唯一状态为 **`ATTRIBUTION_UNRESOLVED`**。

| gate | name | passed | observed | required |
|---|---|---|---|---|
| A | inventory_self_validation | True | 3/3 | 3/3 |
| B | all_required_workers_complete | True | 13/13 | 13/13 |
| C | weakref_old_survivor_absent | True | no old storage | zero |
| D | fixed_topology_controls_constant | False | 3/6 | 6/6 |
| E | edge_adjusted_step_terms_near_zero | True | 4/4 | all D runs |
| F | frozen_first_four_state_regression | True | 4/4 | all D runs |
| STATUS | unique_attribution_status | True | ATTRIBUTION_UNRESOLVED | ["ATTRIBUTED_TO_DYNAMIC_WORKING_SET","INVENTORY_INSTRUMENTATION_BIAS","RETENTION_IDENTIFIED_AND_FIXED","RETENTION_CONFIRMED_UNFIXED","ATTRIBUTION_UNRESOLVED"] |

## 13. Stage 01D2 申请资格

当前结论：**不具备申请新 Stage 01D2 协议的资格**。即使具备资格，本阶段也没有创建或运行 Stage 01D2。

## 14. 历史失败状态保持

Stage 01D 仍为 **`V2_FAIL`**；Stage 01D-R 仍为
**`RESOURCE_FAIL_LINEAR_GROWTH`**。R2 归因不具追溯改写效力。

## 15. V3 与 Stage 02

**V3 未开始，Stage 02 未开始。** 未运行正式 V2 时间/空间收敛，未训练神经网络，
未实现 MLP、Transformer 或 attention。

## 证据索引

| path | SHA-256 | bytes |
|---|---|---|
| `06_experiments/stage_01dr2_storage_attribution/configs/preregistered_storage_attribution.yml` | c281b5ac299fa2f20b71960b86439b21b3a7e10444cd2e7b92ae5ab1ef1fae23 | 4634 |
| `06_experiments/stage_01dr2_storage_attribution/results/campaign_summary.json` | cf612253f5d5cc4c1df142d0e7932c0b8785963341df5a66cdc0cb3393192b76 | 426 |
| `06_experiments/stage_01dr2_storage_attribution/results/inventory_validation_summary.csv` | 04b592c7c24898205856294f4da0d21348a0b08340ba1bbb71422772235115d9 | 367 |
| `06_experiments/stage_01dr2_storage_attribution/results/weakref_lifetime_summary.csv` | 269b227ea5ae9d3f6860a53ae182ce13dc494164baf9c5d00873cb50df2d0441 | 588 |
| `06_experiments/stage_01dr2_storage_attribution/results/fixed_topology_summary.csv` | f8db681193532fb45dcf2d771101d85047cd5cedbea7923ce4ba8e1fd4155933 | 398 |
| `06_experiments/stage_01dr2_storage_attribution/results/edge_working_set_models.csv` | 8f07f85b9166fae2bc5c4aff636f5d93adfcf5dfef49379a7e9a61bdbfb39f92 | 1660 |
| `06_experiments/stage_01dr2_storage_attribution/results/numerical_regression_summary.csv` | 70225824847204f5089292cad8c033a1d505e162ccb0a5812e0ed5410c290670 | 195 |
| `06_experiments/stage_01dr2_storage_attribution/results/attribution_gate_evidence.csv` | ba702b314c015c5d926c29cd4185bb29f624aba2357b455302dbcf6b2c7d7467 | 575 |
| `06_experiments/stage_01dr2_storage_attribution/results/analysis_summary.json` | 61101fff720ba32497c98f06f859b28af658f200acead4b456a38e6bdeeec58d | 705 |
| `06_experiments/stage_01dr2_storage_attribution/results/stage01dr2_attribution_status.txt` | 685009884205f96255875045c59380437b4d3b2c8b12036d11c29344bb433ab9 | 23 |
