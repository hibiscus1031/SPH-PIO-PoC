# Stage 01D-R2 Semantic Storage Attribution

## 语义 ledger

Ledger 在创建/返回边界显式登记 current state、current neighborhood、density/EOS、
pressure、viscosity、RK2 midpoint、diagnostics、archive、monitor 和 unknown；不按 shape
猜测。登记表仅保存 weakref 与标量元数据，storage 按 `(device, data_ptr, nbytes)` 去重。

每个稀疏检查点分别输出 `live_total_bytes`、`current_state_bytes`、
`current_edge_dependent_bytes`、`current_force_workspace_bytes`、`monitor_bytes`、
`unknown_live_bytes` 与 `old_survivor_bytes`。中点位置/速度通过不改变公式的临时
evaluation observer 在创建边界登记；冻结 integrator 源文件没有改动。

## 固定拓扑 B/C

| run | edges | edge values | tensor-count Δ | unknown-byte Δ | old-byte Δ | PASS |
|---|---|---|---|---|---|---|
| stage01dr2_b_r1 | 82944 | 1 | 0 | 0 B (0.000 MB) | 0 B (0.000 MB) | True |
| stage01dr2_b_r2 | 82944 | 1 | 0 | 0 B (0.000 MB) | 0 B (0.000 MB) | True |
| stage01dr2_b_r3 | 82944 | 1 | 0 | 0 B (0.000 MB) | 0 B (0.000 MB) | True |
| stage01dr2_c_r1 | 82940 | 3 | 0 | 0 B (0.000 MB) | 0 B (0.000 MB) | False |
| stage01dr2_c_r2 | 82940 | 3 | 0 | 0 B (0.000 MB) | 0 B (0.000 MB) | False |
| stage01dr2_c_r3 | 82940 | 3 | 0 | 0 B (0.000 MB) | 0 B (0.000 MB) | False |

## 生命周期与持有链

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

明确持有链数量为 `0`。
本阶段记录 `retention_fix_applied=false`。
