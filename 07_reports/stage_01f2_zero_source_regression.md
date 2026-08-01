# Stage 01F2 zero-source regression

在 source adapter 完成后首先关闭 source，并直接委托冻结的原始动态步函数。

| case | steps | state identity | edge identity | force identity | neighborhood builds |
|---|---:|---|---|---|---:|
| N16 zero-flow | 100 | bitwise | bitwise | bitwise | 201 = 201 |
| N16 TGV smoke | 20 | bitwise | bitwise | bitwise | 41 = 41 |
| N32 TGV smoke | 20 | bitwise | bitwise | bitwise | 41 = 41 |

positions、velocities、densities、pressures 的最大绝对差均为 0。pair-force residual、internal-force residual、viscous power 和持久 state tensor schema 均保持身份一致。

结论：**PASS**。无源路径未改变，允许继续 MMS 动态代码路径测试。
