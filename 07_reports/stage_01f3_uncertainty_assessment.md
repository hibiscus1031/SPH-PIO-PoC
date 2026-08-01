# Stage 01F3 uncertainty assessment

1. Stage 01F continuum closure error：已冻结并通过，不是本次失败源。
2. MMS-A closed-reference error：闭式参考身份通过。
3. MMS-B DOP853 trajectory-reference error：Stage 01F2 连续轨迹参考敏感性通过。
4. Semi-discrete temporal-reference error：双容差差很小，但 MMS-B 动态 topology identity 不稳定，使其无法作为资格化半离散时间参考。
5. RK2 temporal error：未运行矩阵，未量化。
6. SPH spatial error：未运行矩阵，未量化。
7. Source stage-discretization error：Stage 01F2 contract 冻结；本阶段未获得正式矩阵证据。
8. Kernel-density/EOS error：仅前置 smoke 检查通过，不能外推为空间误差。
9. Support consistency-path uncertainty：初始 shell margin 为正，但动态 MMS-B 邻域仍切换，是本阶段主导的不确定性/失败源。
10. Float64 与 CPU determinism：前置门通过；正式重复矩阵未运行。
11. Resource-policy uncertainty：前置轨迹通过；完整正式矩阵未运行。

Exact-reference error 未被统一归类为空间误差。GCI not justified。
