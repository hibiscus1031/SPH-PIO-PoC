# Stage 01B 时间收敛报告

## 状态

**NOT RUN — CLOSED BY V1 GATE**

本报告是门控关闭记录，不是时间收敛结果。没有启动固定 Reynolds
数 Taylor–Green vortex（TGV）时间步长序列，没有生成时间收敛轨迹，也没有
从不存在的数据推算收敛率、Richardson 外推值或时间离散 GCI。

## V1 门控为何未放行

固定物理量 TGV 的 V2 时间收敛分支要求 V1 中的核、邻域、制造解算子和守恒
检查先通过。实际 V1 证据不满足这一前置条件：

1. 10% 粒子无序时，核零阶矩的 L2 误差随分辨率
   \(16\rightarrow24\rightarrow32\) 为
   \(1.7911166\times10^{-2}\rightarrow1.7624710\times10^{-2}
   \rightarrow1.9146495\times10^{-2}\)。最高分辨率误差不仅相对 24 反弹，
   也高于 16。证据：
   `06_experiments/stage_01b_operator_verification/results/kernel_moment_metrics.csv`。
2. 10% 粒子无序时，显式物理 \(\nu\) 适配器所用通用 Laplacian 的制造解 L2
   误差为
   \(4.3073936\rightarrow3.0178049\rightarrow3.2766857\)，
   24→32 的观测阶为 \(-0.2860893\)。这不是可接受的单调空间收敛行为。
   证据：
   `06_experiments/stage_01b_operator_verification/results/manufactured_operator_metrics.csv`。
3. 5% 密度扰动下，物理 \(\nu\) Laplacian 的归一化总内力残差在规则粒子
   \(16,24,32\) 网格分别为
   \(1.1034\times10^{-2},7.5918\times10^{-3},5.7610\times10^{-3}\)；
   对应 pair-force residual 也非零。该离散黏性算子在变密度 WCSPH 状态下
   不能据此声称严格动量守恒。证据：
   `06_experiments/stage_01b_operator_verification/results/conservation_audit.csv`。
4. Antuono 压力项在混合正负压力和无序粒子上也出现非零归一化总内力残差；
   例如 10% 无序、\(16,24,32\) 网格分别为
   \(3.8753\times10^{-3},1.6830\times10^{-3},1.0189\times10^{-3}\)。
   证据同上。

邻域审计还发现，上游默认 `verletScale=1.4` 在 \(16^2\) 规则布局产生
5,552 条重复边，并将零阶矩 L2 误差和制造解 Laplacian L2 误差分别放大到
0.2525736 和 20.019825；项目限定的 `verletScale=1.0` 消除了该组重复边，
但并未消除上述 10% 无序和守恒失败。证据：
`06_experiments/stage_01b_operator_verification/results/upstream_default_neighbor_diagnostic.csv`
与
`06_experiments/stage_01b_operator_verification/results/neighborhood_audit.csv`。

## 未执行的时间收敛工作

由于 V1 已失败，以下项目均未执行：

- 不同 \(\Delta t\) 的固定空间分辨率 TGV 运行；
- 预热后多次时间积分或终止时刻对齐比较；
- 速度、动能、密度或涡量误差的时间步长序列；
- 时间观测阶、Richardson 外推或时间 GCI；
- 不同 \(\Delta t\) 下的运行时 Mach、CFL 和稳定性轨迹比较。

`06_experiments/stage_01b_operator_verification/results/integrator_order.csv`
中的标量 ODE 检查表明实际 `symplecticEuler` 接口在该独立问题上的观测阶约为
2.073、2.036 和 2.018。该结果只验证独立 ODE 接口，不能替代耦合 WCSPH
TGV 的时间收敛研究，也不能绕过 V1 算子门控。

## 结论

Stage 01B 时间收敛分支保持关闭。当前没有可报告的 TGV 时间收敛率，时间
离散不确定度为**未估计**，而不是零。只有在后续工作明确修复或替换失败的
空间算子并重新通过 V1 后，才可重新登记并执行新的 V2 时间收敛计划；本阶段
不进行该操作。
