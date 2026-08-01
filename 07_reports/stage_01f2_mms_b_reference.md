# Stage 01F2 MMS-B reference

MMS-B 参考通过 `scipy.integrate.solve_ivp:DOP853` 独立求解连续 unwrapped 粒子坐标；RHS 场评价前才执行周期 wrap。N16/N32 均保存 `t=0, 0.0025, 0.005, 0.01, 0.02` 的参考状态。

| N | baseline vs tighter Linf | baseline vs half-max-step Linf | finite | initial identity |
|---:|---:|---:|---|---|
| 16 | 0 | 6.661338147750939e-16 | yes | bitwise |
| 32 | 0 | 6.661338147750939e-16 | yes | bitwise |

baseline 为 `rtol=1e-12, atol=1e-14`，tighter 为 `rtol=1e-13, atol=1e-15`；maximum step 为 `1.25e-3`，减半检查为 `6.25e-4`。NPZ 包含参数 hash、积分器、容差、maximum step 与代码提交。

结论：reference sensitivity **PASS**。
