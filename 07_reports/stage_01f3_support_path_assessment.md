# Stage 01F3 support path assessment

Increasing-neighbor consistency path 在任何正式空间轨迹前完成冻结：

| N | dx | H/dx | H | initial edges | cutoff margin |
|---:|---:|---:|---:|---:|---:|
| 16 | 0.125 | 4.061553 | 0.507694 | 12544 | 0.061553 |
| 24 | 0.083333 | 4.5 | 0.375 | 39744 | 0.027864 |
| 32 | 0.0625 | 5.049510 | 0.315594 | 82944 | 0.049510 |
| 48 | 0.041667 | 5.5 | 0.229167 | 223488 | 0.114835 |
| 64 | 0.03125 | 6.041381 | 0.188793 | 462848 | 0.041381 |

这些比例均避开初始规则格点 cutoff shell，但 MMS-B N16 半离散运动仍引发动态 edge identity 切换。因此“初始 cutoff margin 安全”不能替代“动态 topology identity 资格”。

正式 increasing-neighbor 与 fixed-ratio 分支均未运行；不能评价 quadrature floor、误差平台或渐近区。GCI not justified。
