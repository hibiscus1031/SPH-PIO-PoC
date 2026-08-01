# Stage 01F3-R — Dynamic-topology semidiscrete reference qualification

## 最终结论

唯一状态：**SEMIDISCRETE_REFERENCE_QUALIFIED_DENSE_EQUIVALENT**。

MMS-B 的半离散时间参考已通过动态拓扑资格认定。可以申请设计 **Stage 01F3B — MMS convergence verification with qualified dense semidiscrete reference**，但本阶段没有启动 Stage 01F3B。

## 1. Stage 01F3 冻结

Stage 01F3 预注册提交 `af6a0331ad2598a4493baa3168b3aae90fd9b0fc`，最终失败证据提交 `2570f6bea1b668feae7bb60e6cb71094e18053bc`。annotated tag `stage-01f3-fail-semidscrete-topology-identity` 指向该失败提交。冻结清单的十项 SHA-256 全部一致，历史唯一状态仍为 `MMS_CONVERGENCE_VERIFICATION_FAIL`；旧报告、数据、轨迹和失败证据均未修改。

## 2. MMS-A 与 MMS-B topology 差异

MMS-A 是常速平移：所有粒子经历相同位移，粒子间周期距离保持不变，所以 Stage 01F3 baseline/tighter 都只有一个 edge identity，edge count 固定为 12544。MMS-B 是空间非均匀的衰减涡旋：不同位置粒子的相对运动改变粒子间距，合法地穿越 `r/H=1`；旧证据因此出现 28/27 个 identity 和 12480–12672 的 edge count。两者差异来自流动运动学，不是结构缺陷。

## 3. cutoff 光滑性

Wendland C4 的 `W`、`dW/dr`、`grad W` 以及冻结 pressure/viscosity 实际 pair expressions 在 cutoff 左侧趋零，支撑外为零。`q=1-1e-10` 的单边加速度贡献仅 `2.384e-50`；不存在有限跳跃。详见 `stage_01f3r_cutoff_smoothness.md`。

## 4. dense all-pairs RHS

独立 dense 路径对全部非自粒子对使用周期最小像和严格 `r<H`，保持冻结 mass、kernel、density、EOS、pressure、viscosity、source adapter、state vector 与周期域。它不调用 neighbor search、不创建 edge identity、不依赖 edge ordering，也未替换生产 sparse solver。

## 5. sparse/dense 等价性

461 个状态覆盖 A/B 初态、至少 20 个旧 baseline 状态、所有 switching 前后状态、cutoff 人工对及随机扰动。density/pressure 最大差为 0；total acceleration 最大 absolute/relative 差分别为 `5.440e-15`/`3.460e-15`，全部 finite，所有硬门 PASS。

## 6. topology event 审计

只读轨迹中识别 216 个无序 cutoff crossing。全部在 `q≈1`，全部 reciprocal，结构缺陷最大值 0；单边 contribution 最大 `1.964e-52`，聚合 RHS 根两侧差最大 `7.950e-10`，没有不可解释的有限跳跃。

## 7. dense DOP853 三层敏感性

MMS-A 与 MMS-B 的 baseline/tighter、tighter/third position 和 velocity Linf 均远低于 `1e-9`。最大全部敏感性为 position `4.108e-15`、velocity `5.385e-14`；所有状态 finite。容差、max_step、nfev、代码/参数/配置 hash 已保存。

## 8. sparse/dense reference 比较

在 41 个共同物理时刻，MMS-B baseline sparse/dense 的 unwrapped position、velocity Linf 分别为 `1.110e-16`、`1.027e-15`；tighter 分别为 `1.110e-16`、`1.332e-15`。density、pressure、total acceleration 也保持舍入量级一致。新 sparse 回放与旧 11 时刻轨迹完全相同，因此旧 topology identity 失败被保留，但不再被误解释为参考状态失败。

## 9. 单一 pilot

仅运行 MMS-B、N16、`dt=2.5e-4`、`t_final=0.01` 的 40 步 RK2 pilot。状态 finite；相对 dense reference 的 position/velocity Linf 为 `1.010e-8`/`1.484e-6`，相对连续 exact trajectory/field 为 `3.439e-5`/`6.531e-3`，均 finite。最大 force assembly defect `4.690e-16`、momentum defect `1.647e-17`、结构缺陷 0；RSS 与 step-time resource policy PASS。未运行其他 dt。

## 10. 唯一参考资格状态

cutoff 实际 pair terms、sparse/dense RHS、topology events、dense 三层敏感性、sparse/dense 参考状态和 pilot 代码路径全部通过，所以唯一状态为 `SEMIDISCRETE_REFERENCE_QUALIFIED_DENSE_EQUIVALENT`，不是 conditional。

## 11. Stage 01F3B 资格

本阶段具备申请设计 Stage 01F3B 的资格。本报告不构成 Stage 01F3B 的预注册，也没有自动启动它。

## 12. 明确未做的分析

没有运行五级 RK2 正式时间矩阵、连续 MMS 时间矩阵或正式空间矩阵；没有计算时间阶、空间阶、Richardson extrapolation 或 GCI。

## 13. 后续阶段状态

Stage 01G、V3 与 Stage 02 仍未开始；未训练网络，未生成标签。

机器可读判定：`06_experiments/stage_01f3r_reference_qualification/results/stage01f3r_evaluation.json`。
