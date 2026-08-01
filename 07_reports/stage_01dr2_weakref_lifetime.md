# Stage 01D-R2 Weakref Lifetime

## 追踪协议

每个 accepted step 对旧 positions/velocities/densities/pressures、midpoint
positions/velocities/neighborhood、start/endpoint neighborhood 及 pressure/viscosity
结果建立 weakref。当前工作集 storage key 会从 old-survivor 集合中排除；age≥2 且
不属于当前 state/neighborhood/workspace 的存活 storage 才算真实旧对象。

## 结果

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

稀疏 `gc.collect()` 后的 old-survivor gate 为
**PASS**。只有确认 survivor 时才运行
脱敏 `gc.get_referrers()`；审计不输出对象内容、路径或局部变量值。
