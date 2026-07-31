# Stage 01D 固定物理动态解验证最终 V2 报告

日期：2026-07-31

## 最终状态

**`V2_FAIL`**

该状态逐字来自
`06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt`，并与
`stage01d_gate_evidence.csv` 的唯一状态行一致。报告生成器不重新判定、
升级或降级 V2，最终状态不存在第四种取值。

## 1. Stage 01C 冻结与 provenance

- 冻结提交：`275fafbb8c8e7ca4fd7384a8ff46b33215b34ced`；
- annotated tag `stage-01c-operator-requalified` 实际解析到 `275fafbb8c8e7ca4fd7384a8ff46b33215b34ced`；
- Stage 01B tag `stage-01b-v1-fail` 实际解析到
  `6f26750fea615c79b08a11fddfd832105b985235`；
- Stage 01C 机器状态：`C1_PASS_C2_PASS_C3_PASS_C4_PASS`；
- SHA-256 清单：43/43 项匹配冻结提交。

这些事实来自冻结清单、git tag 对象和 Stage 01C 状态文件；未修改任何
Stage 00–01C 文件。

## 2. 动态求解器方程和算法

完整状态、周期 wrapping、互易无重复邻域、每阶段重算和 explicit midpoint
实现由 `01_solver/dynamic_solver/` 下八个源文件定义。各源文件实际
SHA-256 收录在本报告证据索引。

时间推进器为 `explicit midpoint RK2`。对同步状态
\((\mathbf x^n,\mathbf v^n)\) 先计算完整起点作用，再构造

\[
\mathbf x^{n+1/2}=\operatorname{wrap}
(\mathbf x^n+\tfrac12\Delta t\,\mathbf v^n),\qquad
\mathbf v^{n+1/2}=\mathbf v^n+
\tfrac12\Delta t\,\mathbf a^n .
\]

中点重新建立周期互易邻域并重新计算密度、EOS 与内部加速度，随后

\[
\mathbf x^{n+1}=\operatorname{wrap}
(\mathbf x^n+\Delta t\,\mathbf v^{n+1/2}),\qquad
\mathbf v^{n+1}=\mathbf v^n+
\Delta t\,\mathbf a^{n+1/2} .
\]

接受步之后再同步终点密度和压力。预登记每步力阶段数为
2；独立 ODE 表负责证明实际阶数，报告
不凭 `RK2` 名称宣称二阶。

## 3. 密度、EOS、压力和黏性形式

完整状态由 `positions`、`velocities`、`masses`、`densities`、
`pressures`、`supports`、周期域和物理时间组成。预登记与实现采用：

\[
\rho_i=\sum_j m_jW_{ij},
\qquad
p_i=c_s^2(\rho_i-\rho_0),
\]

\[
\mathbf f^p_{ij}=
-m_im_j\left(\frac{p_i}{\rho_i^2}+
\frac{p_j}{\rho_j^2}\right)\nabla_iW_{ij},
\]

\[
\mathbf f^\nu_{ij}=
m_im_j\Gamma_{ij}(\mathbf v_j-\mathbf v_i),
\qquad
\Gamma_{ij}=-4*nu/(rho_i+rho_j)*(r_ij dot grad_i(W_ij))/(r_ij^2+(0.01*H_ij)^2).
\]

密度、EOS、压力和两项内部作用在每个完整力阶段重新计算。配置明确记录
`background_pressure=False`、
`pressure_clipping=False`、
`artificial_viscosity=False`、
`particle_shifting=False` 和
`density_diffusion=False`。这些是冻结设计事实；
是否通过由机器 gate 与轨迹样本决定。

## 4. 时间积分器验证

积分器 gate：**PASS**。原始 8 行 ODE
误差与 evaluator 的 fitted/finest-pair order 见
`06_experiments/stage_01d_integrator_verification/results/integrator_verification.csv` 和
`06_experiments/stage_01d_fixed_physics_tgv/results/integrator_gate_evidence.csv`。

| problem | decreases | fitted order | finest pair order | pass |
|---|---|---|---|---|
| scalar_decay | True | 2.041407 | 2.017728 | True |
| coupled_damped_oscillator | True | 1.992673 | 1.996459 | True |

## 5. 零流平衡

零流 gate：**PASS**。

| run_id | protocol | status | N | support family | H/dx | dt | t_final | layout | seed | c_s | mass reference density | EOS reference density | final velocity rel. L2 | final modal rel. error | final energy rel. error | max density fluct. rel. RMS | max Mach | max momentum drift (norm.) | max angular drift (norm.) | min separation/dx | neighbor min | neighbor max | edge count | wall s | mean step s | peak RSS bytes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0 | zero_flow | PASS | 16 | constant_neighbor | 4 | 0.001 | 0.1 | regular | 0 | 20 | 1 | 1.000416 | — | — | — | 4.154664e-16 | 1.267366e-15 | 9.486980e-31 | 6.779273e-32 | 1 | 49 | 49 | 12544 | 4.21359 | 0.02184839 | 2.361590e+08 |

| run_id | last recorded t | velocity L1 | velocity rel. L2 | velocity Linf | modal abs. error | energy abs. error | density fluct. rel. RMS | max Mach | momentum drift abs. | momentum drift norm. | angular drift abs. | angular drift norm. | divergence L2 | viscous power | min separation | neighbor mean | neighbor min | neighbor max | duplicate edges | strict-support omissions | nonreciprocal edges | wall s | peak RSS bytes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0 | 0.1 | 7.992098e-15 | — | 2.534731e-14 | — | 2.738172e-28 | 4.154664e-16 | 1.267366e-15 | 2.958228e-30 | 7.395571e-31 | 1.479114e-31 | 1.848893e-32 | 5.477607e-14 | -6.385014e-28 | 0.125 | 49 | 49 | 49 | 0 | 0 | 0 | 4.191159 | 2.361262e+08 |

| gate | check | passed | observed | threshold | severity | source | detail |
|---|---|---|---|---|---|---|---|
| Z | position_drift | True | 0 | <= 1e-13 | HARD | 06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0.csv | — |
| Z | velocity_linf | True | 2.534731e-14 | <= 1e-12 | HARD | 06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0.csv | — |
| Z | pressure_linf | True | 2.664535e-13 | <= 1e-12 | HARD | 06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0.csv | — |
| Z | relative_density_drift | True | 0 | <= 1e-12 | HARD | 06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0.csv | — |
| Z | zero_flow_100_steps_and_topology | True | {"finite":true,"sample_count":101,"step_complete":true,"topology":{"neighbor_duplicate_edge_count":0.0,"neighbor_missing_self_edge_count":0.0,"neighbor_nonreciprocal_nonself_edge_count":0.0,"neighbor_omitted_strict_support_edge_count":0.0,"neighbor_out_of_bounds_edge_count":0.0,"neighbor_unexpected_edge_count":0.0}} | {"required_steps":100,"topology_counts":0} | HARD | 06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0.csv | spatially uniform initial kernel-summation density; particle masses remain rho0*dx^2 |

## 6. 固定物理 TGV 参数

| parameter | value |
|---|---|
| domain | [-1,1) x [-1,1), periodic |
| rho0 | 1 |
| U0 | 1 |
| L | 2 |
| nu | 0.02 |
| Re | 100 |
| c_s | 20 |
| nominal Ma0 | 0.05 |
| t_final | 0.2 |
| device | cpu |
| dtype | float64 |

解析速度因子为 `exp(-2*nu*pi^2*t)`，能量衰减因子为
`exp(-4*nu*pi^2*t)`。

令
\[
\boldsymbol\phi(\mathbf x)=
[-\sin(\pi x)\cos(\pi y),\ \cos(\pi x)\sin(\pi y)] ,
\]
则代码记录的 TGV modal amplitude 是质量加权投影
\[
A_h(t)=
\frac{\sum_i m_i\,\mathbf v_i(t)\cdot\boldsymbol\phi(\mathbf x_i(t))}
{\sum_i m_i\,\lVert\boldsymbol\phi(\mathbf x_i(t))\rVert^2}.
\]
解析幅值为 \(A(t)=U_0\exp(-2\nu\pi^2t)\)。离散总动能为
\(E_h=\frac12\sum_i m_i\lVert\mathbf v_i\rVert^2\)，轨迹诊断的参考衰减为
\(E_{\mathrm{ref}}(t)=E_h(0)\exp(-4\nu\pi^2t)\)。

## 7. 时间收敛

执行状态：**NOT_RUN**。run summary 中观察到 0/4 个预期轨迹。

未执行或未完成原因（原样来自证据）：`time phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0`。

时间 gate：**NOT_RUN**。解析终点、自收敛 21
共同时间点和平台标志见
`06_experiments/stage_01d_fixed_physics_tgv/results/time_convergence_metrics.csv`。

## 8. 空间收敛

执行状态：**NOT_RUN**。run summary 中观察到 0/3 个预期轨迹。

未执行或未完成原因（原样来自证据）：`space_and_support phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0`。

空间 gate：**NOT_RUN**。三个主误差的
log(error)–log(dx) 斜率、N32/N16 比值、单调性和 `gci_eligible` 全部来自
`06_experiments/stage_01d_fixed_physics_tgv/results/space_convergence_metrics.csv`。
本生成器没有计算 GCI。

## 9. 支撑族比较

执行状态：**NOT_RUN**。run summary 中观察到 0/3 个预期轨迹。

未执行或未完成原因（原样来自证据）：`space_and_support phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0`。

constant- 与 increasing-neighbor 的三个分辨率实际误差、运行时间和邻居数
分别保存在 derived space 表、run summary 与逐轨迹 CSV。没有预设有限
分辨率赢家。

## 10. 动态无序稳健性

执行状态：**NOT_RUN**。run summary 中观察到 0/7 个预期轨迹。

未执行或未完成原因（原样来自证据）：`disorder phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0`。

无序 gate：**NOT_RUN**。regular、5% jitter、
10% jitter 的布局汇总为：

_无可显示字段。_

## 11. Mach/模型形式评估

执行状态：**NOT_RUN**。run summary 中观察到 0/3 个预期轨迹。

未执行或未完成原因（原样来自证据）：`mach phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0`。

Mach gate：**NOT_RUN**。速度误差、密度波动、
最大 Mach、压力、acoustic CFL、wall time 与 RSS 均保存在：

_无可显示字段。_

## 12. 动态守恒

以下数值直接来自所有 accepted 轨迹的保留采样点；压力/黏性 pair 残差与
实际组装的 \(\sum_i m_i\mathbf a_i^{internal}\) 分开报告。

| quantity | extreme | run_id | threshold/role |
|---|---|---|---|
| pressure_relative_pair_force_residual | 0 | zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0 | <= 1e-12 |
| viscosity_relative_pair_force_residual | 0 | zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0 | <= 1e-12 |
| relative_total_internal_force | 5.417404e-18 | smoke_n16_increasing_neighbor_n16_h4p00_dt0p00100000_tf0p010_cs20p0_regular_s0 | <= 1e-10 |
| assembled_relative_internal_force | 5.417404e-18 | smoke_n16_increasing_neighbor_n16_h4p00_dt0p00100000_tf0p010_cs20p0_regular_s0 | <= 1e-10 |
| accumulated_viscous_power | 0 | zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0 | <= 1e-12 |
| pair_direct_viscous_power | 0 | zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0 | <= 1e-12 |
| momentum_drift_absolute | 2.950644e-17 | smoke_n16_increasing_neighbor_n16_h4p00_dt0p00100000_tf0p010_cs20p0_regular_s0 | diagnostic |
| angular_momentum_drift_absolute | 7.632783e-17 | smoke_n16_increasing_neighbor_n16_h4p00_dt0p00100000_tf0p010_cs20p0_regular_s0 | diagnostic |
| minimum_separation | 0.1211847 | smoke_n16_increasing_neighbor_n16_h4p00_dt0p00100000_tf0p010_cs20p0_regular_s0 | diagnostic |
| neighbor_duplicate_edge_count | 0 | zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0 | == 0 |
| neighbor_omitted_strict_support_edge_count | 0 | zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0 | == 0 |
| neighbor_nonreciprocal_nonself_edge_count | 0 | zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0 | == 0 |

机器守恒 gate：**PASS**。角动量是诊断量，
不是对非中心速度差黏性作用的结构守恒声明。

## 13. 自动微分回归

- full-dynamic AD：20/20 行状态为 PASS；
- 1/3/5/8 步最大 AD–FD 相对差：
  `1.148520e-04`；
- 16 步 finite/nonzero：4 行；
- topology claim 原始值：`False`；
- AD gate：**PASS**。

邻域拓扑选择仍按离散、非光滑过程处理。

## 14. 资源使用

预登记停止线为 peak RSS
`8000000000`
bytes、无 checkpoint 单实验预计
`7200`
seconds、后半段热降频增长
`0.3`。

| run_id | protocol | status | particles | edges | wall s | mean step s | peak RSS | thermal slowdown | memory pressure | RSS growth |
|---|---|---|---|---|---|---|---|---|---|---|
| smoke_n16_increasing_neighbor_n16_h4p00_dt0p00100000_tf0p010_cs20p0_regular_s0 | smoke_n16 | PASS | 256 | 12032 | 0.4624282 | 0.02217187 | 2.323415e+08 | 0.01501705 | False | False |
| smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 | smoke_n32 | FAIL | 1024 | 76640 | 0.6901544 | 0.07753339 | 3.244032e+08 | -0.0255588 | False | True |
| zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0 | zero_flow | PASS | 256 | 12544 | 4.21359 | 0.02184839 | 2.361590e+08 | 0.002199797 | False | False |

资源 gate：**FAIL**。

## 15. 失败和限制

| run_id | protocol | status | failure class | failure reason | step | time | failure evidence |
|---|---|---|---|---|---|---|---|
| smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 | smoke_n32 | FAIL | MEMORY_GROWTH | sustained current RSS growth | 4 | 0.002 | 06_experiments/stage_01d_fixed_physics_tgv/logs/smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0_failure.txt |

缺失或被硬门阻断的分支已在第 7–11 节标为 `NOT_RUN` 或
`PARTIAL — REMAINDER NOT_RUN`，并只引用机器证据中的原因。未记录的原因
明确保持“不可推断”，不补写有利解释。provenance gate：
**PASS**。

## 16. 当前 V0/V1/V2/V3 状态

| level | current status | direct evidence |
|---|---|---|
| V0 | CONDITIONAL PASS | 07_reports/stage_01_scope_reclassification.md |
| V1 | REQUALIFIED — C1/C2/C3/C4 PASS | 06_experiments/stage_01c_operator_candidates/results/stage01c_gate_status.txt |
| V2 | V2_FAIL | 06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt |
| V3 | NOT STARTED | 07_reports/stage_01_scope_reclassification.md |

## 17. 是否允许进入 V3

**不允许由本报告放行 V3。** 当前唯一 V2 状态为 `V2_FAIL`；只有新的、明确授权才能改变该边界。

## 18. Stage 02 状态

**Stage 02 仍未开始。** 本阶段没有训练神经网络，没有实现
MLP/Transformer/attention，没有生成学习标签，也没有定义教师或学生求解器。
本报告不构成 Stage 02 授权。

## 19. 完整 V2 gate 矩阵

| gate | check | passed | observed | threshold | severity | source | detail |
|---|---|---|---|---|---|---|---|
| I | scalar_decay_second_order | True | {"decreases":true,"finest_pair_order":2.017727908586886,"fitted_order":2.0414066768743058} | {"finest_pair_order_minimum":1.75,"fitted_order_minimum":1.8} | HARD | 06_experiments/stage_01d_integrator_verification/results/integrator_verification.csv | — |
| I | coupled_damped_oscillator_second_order | True | {"decreases":true,"finest_pair_order":1.9964594041753698,"fitted_order":1.992672681349704} | {"finest_pair_order_minimum":1.75,"fitted_order_minimum":1.8} | HARD | 06_experiments/stage_01d_integrator_verification/results/integrator_verification.csv | — |
| I | both_ode_integrator_gates | True | 2/2 | 2/2 | HARD | 06_experiments/stage_01d_integrator_verification/results/integrator_verification.csv | — |
| Z | position_drift | True | 0 | <= 1e-13 | HARD | 06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0.csv | — |
| Z | velocity_linf | True | 2.534731e-14 | <= 1e-12 | HARD | 06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0.csv | — |
| Z | pressure_linf | True | 2.664535e-13 | <= 1e-12 | HARD | 06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0.csv | — |
| Z | relative_density_drift | True | 0 | <= 1e-12 | HARD | 06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0.csv | — |
| Z | zero_flow_100_steps_and_topology | True | {"finite":true,"sample_count":101,"step_complete":true,"topology":{"neighbor_duplicate_edge_count":0.0,"neighbor_missing_self_edge_count":0.0,"neighbor_nonreciprocal_nonself_edge_count":0.0,"neighbor_omitted_strict_support_edge_count":0.0,"neighbor_out_of_bounds_edge_count":0.0,"neighbor_unexpected_edge_count":0.0}} | {"required_steps":100,"topology_counts":0} | HARD | 06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0.csv | spatially uniform initial kernel-summation density; particle masses remain rho0*dx^2 |
| C | pressure_pair_residual | True | 0 | <= 1e-12 | HARD | results/trajectory_samples/*.csv | — |
| C | viscosity_pair_residual | True | 0 | <= 1e-12 | HARD | results/trajectory_samples/*.csv | — |
| C | reconstructed_total_internal_force | True | 5.417404e-18 | <= 1e-10 | HARD | results/trajectory_samples/*.csv | — |
| C | assembled_mass_weighted_internal_force | True | 5.417404e-18 | <= 1e-10 | HARD | results/trajectory_samples/*.csv | — |
| C | assembly_force_consistency | True | 0 | <= 1.4210854715202004e-14 | HARD | results/trajectory_samples/*.csv | — |
| C | viscous_power_nonpositive | True | 0 | <= 1e-12 | HARD | results/trajectory_samples/*.csv | — |
| C | all_accepted_samples_finite_and_topology_exact | True | {"accepted_runs":2,"accepted_samples":112,"topology":{"neighbor_duplicate_edge_count":[0.0,""],"neighbor_missing_self_edge_count":[0.0,""],"neighbor_nonreciprocal_nonself_edge_count":[0.0,""],"neighbor_omitted_strict_support_edge_count":[0.0,""],"neighbor_out_of_bounds_edge_count":[0.0,""],"neighbor_unexpected_edge_count":[0.0,""]}} | all finite; every topology defect count = 0 | HARD | results/trajectory_samples/*.csv | — |
| T | four_time_trajectories_finite | False | NOT_RUN | True | NOT_RUN | results/time_convergence_metrics.csv | time phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| T | analytic_endpoint_credible_decrease | False | NOT_RUN | at least one selected finest/coarsest ratio <= None | NOT_RUN | results/time_convergence_metrics.csv | time phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| T | velocity_self_convergence_credible_decrease | False | NOT_RUN | <= None | NOT_RUN | results/time_convergence_metrics.csv | time phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| T | analytic_or_self_time_trend | False | NOT_RUN | analytic OR self trend passes | NOT_RUN | results/time_convergence_metrics.csv | time phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| S | primary_selected_spatial_slopes_positive | False | NOT_RUN | all three fitted slopes > 0 | NOT_RUN | results/space_convergence_metrics.csv | space_and_support phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| S | primary_velocity_n32_over_n16 | False | NOT_RUN | <= None | NOT_RUN | results/space_convergence_metrics.csv | space_and_support phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| S | primary_space_gate | False | NOT_RUN | positive slopes and velocity N32/N16 gate | NOT_RUN | results/space_convergence_metrics.csv | space_and_support phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| S | conditional_time_pass_space_plateau | False | NOT_RUN | time complete/finite/credible; space complete; primary nonworsening plateau; support evidence complete | NOT_RUN | results/time_convergence_metrics.csv + results/space_convergence_metrics.csv | space_and_support phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| S | both_support_families_complete | False | NOT_RUN | 3 regular trajectories per support family | NOT_RUN | results/space_convergence_metrics.csv | space_and_support phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| AD | dynamic_current_20_of_20 | True | {"metadata_pass":true,"pass_count":20,"raw_recomputed_declarations":true,"row_count":20,"short_max_relative_difference":0.00011485198607266744,"step16":true,"topology_disclaimed":true} | 20/20 recomputed from raw AD/FD; short <= 0.01; step16 finite nonzero; topology false; metadata exact | HARD | 06_experiments/stage_01d_fixed_physics_tgv/results/dynamic_autograd_fd.csv | — |
| AD | stage01c_current_regression_20_of_20 | True | {"metadata_pass":true,"pass_count":20,"raw_recomputed_declarations":true,"row_count":20,"short_max_relative_difference":1.6190766511573288e-05,"step16":true,"topology_disclaimed":true} | 20/20 recomputed from raw AD/FD; short <= 0.01; step16 finite nonzero; topology false; metadata exact | HARD | 06_experiments/stage_01d_fixed_physics_tgv/results/stage01c_autograd_regression.csv | — |
| AD | stage01c_frozen_baseline_20_of_20 | True | {"metadata_pass":true,"pass_count":20,"raw_recomputed_declarations":true,"row_count":20,"short_max_relative_difference":1.6190766511573288e-05,"step16":true,"topology_disclaimed":true} | 20/20 recomputed from raw AD/FD; short <= 0.01; step16 finite nonzero; topology false; metadata exact | HARD | 06_experiments/stage_01c_autograd/results/native_autograd_fd.csv | — |
| AD | current_stage01c_matches_frozen_case_keys | True | {"parameter_step_keys_match":true,"parameter_values_and_fd_steps_match":true} | {"parameter_step_keys_match":true,"parameter_values_and_fd_steps_match":true} | HARD | results/stage01c_autograd_regression.csv + stage_01c_autograd/results/native_autograd_fd.csv | — |
| SMOKE | n16_and_n32_smoke | False | {"execution_status":"COMPLETE","n16":true,"n32":false,"run_ids":{"n16":"smoke_n16_increasing_neighbor_n16_h4p00_dt0p00100000_tf0p010_cs20p0_regular_s0","n32":"smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0"}} | both pass complete core sample gates | HARD | results/trajectory_samples/*.csv | — |
| D | regular_disorder_control | False | NOT_RUN | True | NOT_RUN | results/disorder_summary.csv | disorder phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| D | jitter_05_disorder_control | False | NOT_RUN | True | NOT_RUN | results/disorder_summary.csv | disorder phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| D | jitter_10_velocity_error_multiplier | False | NOT_RUN | <= None | NOT_RUN | results/disorder_summary.csv | disorder phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| D | all_disorder_layouts_robust | False | NOT_RUN | all pre-registered runs pass core and clustering gates | NOT_RUN | results/disorder_summary.csv | disorder phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| D | conditional_disorder_regular_and_jitter05_only | False | NOT_RUN | PASS if all layouts pass; CONDITIONAL only if regular and 5% pass while 10% fails with sampled failure evidence | NOT_RUN | results/disorder_summary.csv | disorder phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| M | three_mach_runs_quantified | False | NOT_RUN | all c_s={10,20,40} finite with error/density/cost evidence | NOT_RUN | results/mach_summary.csv | mach phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| M | conditional_quantified_model_form_error_dominant | False | NOT_RUN | three complete/core-passing Mach runs and a strict velocity-error decrease as Mach decreases | NOT_RUN | results/mach_summary.csv | mach phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| R | peak_rss | True | {"archive_rss_failure_class_run_ids":[],"effective_peak_rss_bytes":324403200.0,"sample_peak_rss_bytes":324386816.0,"summary_missing_or_nonfinite_run_ids":[],"summary_post_archive_peak_rss_bytes":324403200.0} | <= 8000000000 | HARD | results/run_summary.csv + trajectory_samples/*.csv | — |
| R | thermal_slowdown | True | 0.05882581 | <= 0.3 | HARD | results/run_summary.csv + trajectory_samples/*.csv | — |
| R | minimum_separation_over_dx | True | 0.9694777 | >= 0.25 | HARD | results/run_summary.csv + trajectory_samples/*.csv | — |
| R | sustained_memory_pressure_policy | True | {"flagged_runs":[],"missing_runs":[]} | {"allowed_flagged_runs":0,"consecutive_samples":2,"free_percentage_below":10.0} | HARD | run_summary flags or trajectory sample memory series | — |
| R | sustained_current_rss_growth_policy | False | {"flagged_runs":["smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0"],"missing_runs":[]} | {"allowed_flagged_runs":0,"consecutive_strict_increases":4,"minimum_absolute_increase_bytes":50000000,"minimum_fractional_increase":0.25} | HARD | run_summary flags or trajectory sample current RSS series | — |
| R | resource_and_unexplained_failure_gate | False | {"core_nonaccepted":["smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0"],"hard_scope_states_finite":true,"memory_growth_ok":false,"memory_pressure_ok":true,"unexplained":[]} | all preregistered resource stop conditions clear | HARD | results/run_summary.csv + trajectory_samples/*.csv | — |
| P | prerequisite_execution_order_and_evidence_identity | True | {"execution_order_first_two":["independent scalar and coupled-ODE integrator verification","100-step regular zero-flow equilibrium"],"integrator_identity":true,"master_config_sha256":"7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0","run_git_identity":true} | integrator then zero-flow; one exact git identity; integrator config hash equals current preregistration | HARD | 06_experiments/stage_01d_fixed_physics_tgv/configs/preregistered_primary_tgv.yml | — |
| P | configuration_logs_and_failure_evidence_retained | True | {"actual_master_preregistration_sha256":"7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0","config_and_git_hashes_complete":true,"execution_order_first_two":["independent scalar and coupled-ODE integrator verification","100-step regular zero-flow equilibrium"],"expected_git_hash":"3290b65837805ae5aa15f98580ffcd7e002161ba","failed_run_count":1,"failure_evidence_missing_count":0,"failure_evidence_present_count":1,"integrator_identity_pass":true,"missing_trajectory_state_run_ids":[],"pass":true,"preregistration_revision":6,"preregistration_revision_at_least_5":true,"preregistration_status_exact":true,"prerequisite_execution_order_pass":true,"recorded_paths_relative_only":true,"resolved_config_mismatch_run_ids":[],"resolved_config_verified_count":3,"run_count":3,"run_git_identity_pass":true,"sample_table_count":3,"source_trees_clean":true,"stderr_log_missing_count":0,"stderr_log_present_count":3,"stdout_log_missing_count":0,"stdout_log_present_count":3,"trajectory_state_count":3,"unique_run_git_hashes":["3290b65837805ae5aa15f98580ffcd7e002161ba"]} | all hashes/logs and failed-run evidence present | HARD | results/run_summary.csv | — |
| V2 | decision_hard_time_four_finite | False | NOT_RUN | True | NOT_RUN | derived from prior gate rows | time phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| V2 | decision_hard_time_credible_trend | False | NOT_RUN | True | NOT_RUN | derived from prior gate rows | time phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| V2 | decision_hard_primary_space | False | NOT_RUN | True | NOT_RUN | derived from prior gate rows | space_and_support phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| V2 | decision_hard_support_family_complete | False | NOT_RUN | True | NOT_RUN | derived from prior gate rows | space_and_support phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| V2 | decision_hard_smoke | False | False | True | HARD | derived from prior gate rows | failure-priority decision input |
| V2 | decision_hard_disorder_complete | False | NOT_RUN | True | NOT_RUN | derived from prior gate rows | disorder phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| V2 | decision_hard_regular_disorder_control | False | NOT_RUN | True | NOT_RUN | derived from prior gate rows | disorder phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| V2 | decision_hard_jitter_05_disorder_control | False | NOT_RUN | True | NOT_RUN | derived from prior gate rows | disorder phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| V2 | decision_hard_mach_quantified | False | NOT_RUN | True | NOT_RUN | derived from prior gate rows | mach phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| V2 | decision_hard_resources_and_clustering | False | False | True | HARD | derived from prior gate rows | failure-priority decision input |
| V2 | decision_hard_disorder_outcome_qualified | False | NOT_RUN | True | NOT_RUN | derived from prior gate rows | disorder phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| V2 | unique_final_status | False | V2_FAIL | V2_PASS; conditional/failure rules explicit | STATUS | preregistered_primary_tgv.yml | {"conditional_checks": {"quantified_model_form_error_dominant": false, "regular_and_jitter05_pass_jitter10_fails": false, "time_pass_space_plateau": false}, "effective_hard_checks": {"autograd": true, "disorder_complete": false, "disorder_outcome_qualified": false, "dynamic_conservation": true, "integrator": true, "jitter_05_disorder_control": false, "mach_quantified": false, "primary_space": false, "provenance": true, "regular_disorder_control": false, "resources_and_clustering": false, "smoke": false, "support_family_complete": false, "time_credible_trend": false, "time_four_finite": false, "zero_flow": true}, "raw_hard_checks": {"autograd": true, "disorder_complete": false, "dynamic_conservation": true, "integrator": true, "jitter_05_disorder_control": false, "mach_quantified": false, "primary_space": false, "provenance": true, "regular_disorder_control": false, "resources_and_clustering": false, "smoke": false, "support_family_complete": false, "time_credible_trend": false, "time_four_finite": false, "zero_flow": true}} |

## 20. 证据索引

下表给出本报告实际读取或直接引用的主证据路径、内容 SHA-256 与字节数。
路径均为项目相对路径，不写入用户名或主目录。

| evidence path | SHA-256 | bytes |
|---|---|---|
| `01_solver/dynamic_solver/acceleration.py` | `9835e5a67b177d1991ba8fab80109dc1ab5ea1d783a403b1c8b391d3b809771e` | 6575 |
| `01_solver/dynamic_solver/density.py` | `43af02afe7797ebd21cd3a34a95c329105e18746d56fe6685178e8204a52ada0` | 2664 |
| `01_solver/dynamic_solver/diagnostics.py` | `f1f39d9fb1edc547fb051aa34524894ec3239a4c375c15c6f1ac42367f7ae5a7` | 51316 |
| `01_solver/dynamic_solver/equation_of_state.py` | `41fcc2f67b35f6e3997d790e3461027d09a9a211a30f9681cd2dcf0996b78e57` | 2512 |
| `01_solver/dynamic_solver/integrator.py` | `d26550919e90d711548dd352880dd490e7cea7327f25a70a6f9c93da045ae956` | 3920 |
| `01_solver/dynamic_solver/periodic_rollout.py` | `95453a1726185c5cc8f65d67ae867a366e4e0dfc10dddcc3570b9fa7c9abe1e4` | 5412 |
| `01_solver/dynamic_solver/state.py` | `8df0c49aee8271fe9c107f4776e4ce4e3c8f35e68584261c0efa34cc9eda0561` | 3866 |
| `01_solver/dynamic_solver/taylor_green.py` | `d918ab43e70255825cc2b4bedca06432bdeecac9d07325c160da80dc8c0ab4bd` | 6912 |
| `06_experiments/stage_01c_autograd/results/native_autograd_fd.csv` | `8a5dae3187f66ce698ea3a59554e30766d90796ec8e19b1f82454218fe7ef5aa` | 4556 |
| `06_experiments/stage_01c_operator_candidates/results/stage01c_gate_status.txt` | `b8ca179abb637e75affaf8010149468eca984e1d21524a9f68b5ed49f107c8d7` | 32 |
| `06_experiments/stage_01d_fixed_physics_tgv/configs/preregistered_primary_tgv.yml` | `7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0` | 11213 |
| `06_experiments/stage_01d_fixed_physics_tgv/generate_stage01d_reports.py` | `e1c284f1a09096d47c409b1e2c191962e0688ac63c717d7e71f31e77ac366f3d` | 90421 |
| `06_experiments/stage_01d_fixed_physics_tgv/logs/smoke_n16_increasing_neighbor_n16_h4p00_dt0p00100000_tf0p010_cs20p0_regular_s0_config.json` | `5b977bb4cefc78a35533734b114c4f8604690e00571523c94c73434582c9bf7e` | 2660 |
| `06_experiments/stage_01d_fixed_physics_tgv/logs/smoke_n16_increasing_neighbor_n16_h4p00_dt0p00100000_tf0p010_cs20p0_regular_s0_stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |
| `06_experiments/stage_01d_fixed_physics_tgv/logs/smoke_n16_increasing_neighbor_n16_h4p00_dt0p00100000_tf0p010_cs20p0_regular_s0_stdout.log` | `a1d989eee4b71fb09927aa3dc39c69d245738e5ed985e55d31c1555ce24ab8af` | 59012 |
| `06_experiments/stage_01d_fixed_physics_tgv/logs/smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0_config.json` | `31e548205c884854396a4a2131e8237b86ce529da2ac559ee21eee640f5a49b8` | 2895 |
| `06_experiments/stage_01d_fixed_physics_tgv/logs/smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0_failure.txt` | `dd94eceeeeb4e380c4aaebb262f38ae4aae6d6e83a77d00b3be3dd85ee77ad5e` | 241 |
| `06_experiments/stage_01d_fixed_physics_tgv/logs/smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0_stderr.log` | `dd94eceeeeb4e380c4aaebb262f38ae4aae6d6e83a77d00b3be3dd85ee77ad5e` | 241 |
| `06_experiments/stage_01d_fixed_physics_tgv/logs/smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0_stdout.log` | `de58abcd9e794466282f09666ca6396325a62c6e343d96f289118ee17ccb2556` | 26539 |
| `06_experiments/stage_01d_fixed_physics_tgv/logs/zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0_config.json` | `9c7ca62c4932cc616156f06eba7ad8faef353cf7ea874c0133faa51e3f61d78b` | 4547 |
| `06_experiments/stage_01d_fixed_physics_tgv/logs/zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0_stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |
| `06_experiments/stage_01d_fixed_physics_tgv/logs/zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0_stdout.log` | `80a49a04abb3b1b91ec9d272229bbde81d73429cc423e61fe1df8c65781ab4db` | 532932 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/disorder_summary.csv` | `c47df9515fc73976f30339db3e21fade00ea54a6063266d630994122431ff21c` | 337 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/dynamic_autograd_fd.csv` | `b697887261913b7b6d54ddfb27be7ef8719af7639f059989086b559637a8e431` | 8280 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/integrator_gate_evidence.csv` | `6df650601d9454f9268180c5c31c691c1a8c44c7b7f19084e168ba3a841fb1ad` | 622 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/mach_summary.csv` | `e72883fcc5dee437e68d6e38bed78574e76cf6d44c0a66d1bddfb291cb165027` | 329 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/run_summary.csv` | `74f96bd7d9bbb3cecb164221a6ac8d1c8eb9502b06aefe670bb530f41df47a06` | 6532 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/space_convergence_metrics.csv` | `d4c27789ac7b405c310e0a94a27bed728c7f6c52514ce80a9e301d35075eea09` | 355 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01c_autograd_regression.csv` | `4d50875afb945075af9b9e524bfb6d9f95f25abd69d630aa58ae9cebc0c99a85` | 7307 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01c_sha256_manifest.csv` | `46a66c51863c10eb07db1c57401ee8008a5335e20cd54bf132cb5d9337bcdcc2` | 10979 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_gate_evidence.csv` | `fbcb0a2e0b8d0f97c39da2c2b2d1fec5e918e5ea046cf7548f19670b48e411a3` | 17101 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt` | `7bd1685c7a729a27af2b89caf66a1a5fbaecaa951ae47f26406b58636df0dc1e` | 8 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/time_convergence_metrics.csv` | `31ff2fc54e03cdd550457cf3818db25c2933642bde561e7cd2e646092589e94d` | 329 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/smoke_n16_increasing_neighbor_n16_h4p00_dt0p00100000_tf0p010_cs20p0_regular_s0.csv` | `c9ed548fd816ee96960ed0e6029347de2f18a893f9e2e0f33492723ce27d486c` | 23599 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0.csv` | `3a14895da85a32dc70bfd1a6c1738b484a3cea20038d2a5ac1bc4fa86f9cbb61` | 12036 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0.csv` | `e0ac5be242e2ce6c5554c9145f89dac56e51f70fe323913b7cc6f9bd5ee81c9d` | 182665 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_states/smoke_n16_increasing_neighbor_n16_h4p00_dt0p00100000_tf0p010_cs20p0_regular_s0.npz` | `96c7390142736249d385eefa2d01dd0f07026d6e94229c1b7b8e117db2eb185c` | 42560 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_states/smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0.npz` | `11e8d9f8a43924f0e95ca2ccecb9b785fcd3fa40ff2ce4806b593993efa79779` | 71893 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_states/zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0.npz` | `38aa5961c304705e9033d4aa7178452125eb11c504fc0c21501a598a0ad5518c` | 403542 |
| `06_experiments/stage_01d_integrator_verification/results/integrator_verification.csv` | `dcfba86b69e6ff2fad4d9325d4b93a8b0916d3f4be3c7eca6fe530b96073217b` | 2118 |
| `07_reports/stage_01_scope_reclassification.md` | `e16fb922e66993057aa5dd7d20f529be8d24ed3ae72d2042a2b53bbbc3611e56` | 3945 |
| `07_reports/stage_01c_final_requalification.md` | `d17e8375a1365edc133d226063413f3d7bc22f4ffd841b7caae4fb82dc964c6b` | 15071 |

## 最终声明

唯一最终状态保持为 **`V2_FAIL`**；Stage 02 未开始。
