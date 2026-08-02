# Stage 01F3C N32 半离散参考

## 冻结与方法

Stage 01F3B 冻结提交为 `5a0ef2556a7128865f07d60abcd54666ca5fba47`，历史状态保持 `MMS_CONVERGENCE_VERIFICATION_FAIL`。新参考使用 production sparse SPH RHS 与 SciPy DOP853，不使用项目 RK2。

## 三重参考与 sparse/dense 抽查

| run | solution | N | b/t pos Linf | b/t vel Linf | t/3 pos Linf | t/3 vel Linf | sparse/dense abs | sparse/dense rel | nfev b/t/3 | status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| f3c_ref_n32_a | MMS_A | 32 | 4.330e-15 | 1.588e-13 | 5.440e-15 | 1.726e-13 | 9.881e-15 | 1.512e-13 | 7745/15437/30797 | PASS |
| f3c_ref_n32_b | MMS_B | 32 | 4.219e-15 | 1.533e-13 | 6.550e-15 | 1.569e-13 | 1.010e-14 | 1.088e-15 | 7745/15437/30797 | PASS |

三条容差路径状态均 finite；拓扑结构缺陷为 0，切换保持 reciprocal。每个解在至少 10 个状态上完成 sparse/dense total-acceleration 抽查。NPZ、配置、参数与代码 SHA-256 均记录于对应 run summary。
