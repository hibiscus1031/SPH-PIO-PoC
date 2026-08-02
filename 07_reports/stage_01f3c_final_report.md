# Stage 01F3C 最终报告

## 1. Stage 01F3B 冻结

冻结提交 `5a0ef2556a7128865f07d60abcd54666ca5fba47`，annotated tag `stage-01f3b-fail-continuous-velocity-ct2`，SHA-256 清单与状态核验 `PASS`。

## 2. 旧 CT2 的形式失败

旧 CT2 要求 total exact velocity error 非增；MMS-A 从 `0.002593687534388588` 增至 `0.002593997366237996`，MMS-B 从 `0.002599595258802144` 增至 `0.002599676260560093`，故 Stage 01F3B 形式失败。

## 3. N32 半离散 DOP853 参考

| run | solution | N | b/t pos Linf | b/t vel Linf | t/3 pos Linf | t/3 vel Linf | sparse/dense abs | sparse/dense rel | nfev b/t/3 | status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| f3c_ref_n32_a | MMS_A | 32 | 4.330e-15 | 1.588e-13 | 5.440e-15 | 1.726e-13 | 9.881e-15 | 1.512e-13 | 7745/15437/30797 | PASS |
| f3c_ref_n32_b | MMS_B | 32 | 4.219e-15 | 1.533e-13 | 6.550e-15 | 1.569e-13 | 1.010e-14 | 1.088e-15 | 7745/15437/30797 | PASS |

## 4. total/space/time 向量分解

向量证据在每个粒子、每个共同物理时刻保存；N32 分解状态 `FAIL`。

## 5. 交叉项与误差抵消

N32 cancellation gate `FAIL`；held-out cancellation gate `FAIL`。平方范数按 `||e_total||²=||e_space||²+||e_time||²+2<e_space,e_time>` 复核。

## 6. 时间误差独立阶次

- MMS_A: endpoint time order `1.773032`, integrated time order `2.026856`, finest platform distance `0.000093%`, closure abs `0.000e+00`, status `FAIL`.
- MMS_B: endpoint time order `2.037201`, integrated time order `2.018096`, finest platform distance `0.000069%`, closure abs `4.337e-19`, status `FAIL`.

## 7. 空间平台距离

最细层相对距离列于上述摘要，门限固定为 1%。

## 8. Held-out N24 确认

- MMS_A: endpoint time order `2.020623`, integrated time order `2.013895`, finest platform distance `0.000337%`, status `FAIL`.
- MMS_B: endpoint time order `2.010929`, integrated time order `2.008204`, finest platform distance `0.000335%`, status `FAIL`.

## 9. Source、守恒、拓扑、资源和确定性

综合状态 `PASS`；最大 pair residual `0.000e+00`，internal residual `1.965e-17`，assembly defect `3.152e-16`，momentum defect `1.306e-17`，peak RSS `288915456` bytes。

## 10. 唯一 Stage 01F3C 状态

`CT2_MIXED_OR_UNRESOLVED`

## 11. Stage 01F3D 申请资格

当前不具备申请设计 `Stage 01F3D — Plateau-aware MMS convergence requalification`。Stage 01F3D 未自动启动。

## 12. Stage 01F3B 历史状态

历史状态仍为 `MMS_CONVERGENCE_VERIFICATION_FAIL`，未修改、未放宽、未重算、未重分类。

## 13. 下游范围

Stage 01G、V3、Stage 02、训练与学习标签均未开始；Stage 01G 申请仍不允许。
