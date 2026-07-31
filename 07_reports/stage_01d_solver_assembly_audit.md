# Stage 01D 动态求解器组装审计

日期：2026-07-31

最终 V2 状态文件记录：**`V2_FAIL`**。本报告只审计组装、
冻结 provenance 和已有机器 gate，不重新运行 TGV。

## 1. Stage 01C 冻结与 provenance

| item | expected | observed |
|---|---|---|
| Stage 01C commit | 275fafbb8c8e7ca4fd7384a8ff46b33215b34ced | 275fafbb8c8e7ca4fd7384a8ff46b33215b34ced |
| Stage 01C annotated tag | 275fafbb8c8e7ca4fd7384a8ff46b33215b34ced | 275fafbb8c8e7ca4fd7384a8ff46b33215b34ced |
| Stage 01B tag | 6f26750fea615c79b08a11fddfd832105b985235 | 6f26750fea615c79b08a11fddfd832105b985235 |
| manifest matches | 43 | 43 |

Stage 01C 机器状态为 `C1_PASS_C2_PASS_C3_PASS_C4_PASS`。冻结清单共
43 项，其中 43 项存在、43
项与冻结提交 SHA-256 一致。若这些数字不相等，事实会保留在本表，不能被
报告文字改写为通过。

## 2. 状态、密度、EOS 和内部作用

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

## 3. 二阶显式中点组装

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

## 4. 零流平衡证据

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

## 5. 动态守恒和耗散

以下极值直接遍历 run summary 中所有 accepted 轨迹的每个保留采样点。
角动量仅作诊断；Stage 01C 已说明速度差黏性作用不保证逐 pair 中心力。

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

| gate | check | passed | observed | threshold | severity | source | detail |
|---|---|---|---|---|---|---|---|
| C | pressure_pair_residual | True | 0 | <= 1e-12 | HARD | results/trajectory_samples/*.csv | — |
| C | viscosity_pair_residual | True | 0 | <= 1e-12 | HARD | results/trajectory_samples/*.csv | — |
| C | reconstructed_total_internal_force | True | 5.417404e-18 | <= 1e-10 | HARD | results/trajectory_samples/*.csv | — |
| C | assembled_mass_weighted_internal_force | True | 5.417404e-18 | <= 1e-10 | HARD | results/trajectory_samples/*.csv | — |
| C | assembly_force_consistency | True | 0 | <= 1.4210854715202004e-14 | HARD | results/trajectory_samples/*.csv | — |
| C | viscous_power_nonpositive | True | 0 | <= 1e-12 | HARD | results/trajectory_samples/*.csv | — |
| C | all_accepted_samples_finite_and_topology_exact | True | {"accepted_runs":2,"accepted_samples":112,"topology":{"neighbor_duplicate_edge_count":[0.0,""],"neighbor_missing_self_edge_count":[0.0,""],"neighbor_nonreciprocal_nonself_edge_count":[0.0,""],"neighbor_omitted_strict_support_edge_count":[0.0,""],"neighbor_out_of_bounds_edge_count":[0.0,""],"neighbor_unexpected_edge_count":[0.0,""]}} | all finite; every topology defect count = 0 | HARD | results/trajectory_samples/*.csv | — |

## 6. 完整动态自动微分

| quantity | observed |
|---|---:|
| dynamic AD rows | 20 |
| dynamic AD PASS rows | 20 |
| 1/3/5/8-step maximum relative difference | 1.148520e-04 |
| 16-step finite and nonzero rows | 4 |
| topology differentiability claim values | False |

| gate | check | passed | observed | threshold | severity | source | detail |
|---|---|---|---|---|---|---|---|
| AD | dynamic_current_20_of_20 | True | {"metadata_pass":true,"pass_count":20,"raw_recomputed_declarations":true,"row_count":20,"short_max_relative_difference":0.00011485198607266744,"step16":true,"topology_disclaimed":true} | 20/20 recomputed from raw AD/FD; short <= 0.01; step16 finite nonzero; topology false; metadata exact | HARD | 06_experiments/stage_01d_fixed_physics_tgv/results/dynamic_autograd_fd.csv | — |
| AD | stage01c_current_regression_20_of_20 | True | {"metadata_pass":true,"pass_count":20,"raw_recomputed_declarations":true,"row_count":20,"short_max_relative_difference":1.6190766511573288e-05,"step16":true,"topology_disclaimed":true} | 20/20 recomputed from raw AD/FD; short <= 0.01; step16 finite nonzero; topology false; metadata exact | HARD | 06_experiments/stage_01d_fixed_physics_tgv/results/stage01c_autograd_regression.csv | — |
| AD | stage01c_frozen_baseline_20_of_20 | True | {"metadata_pass":true,"pass_count":20,"raw_recomputed_declarations":true,"row_count":20,"short_max_relative_difference":1.6190766511573288e-05,"step16":true,"topology_disclaimed":true} | 20/20 recomputed from raw AD/FD; short <= 0.01; step16 finite nonzero; topology false; metadata exact | HARD | 06_experiments/stage_01c_autograd/results/native_autograd_fd.csv | — |
| AD | current_stage01c_matches_frozen_case_keys | True | {"parameter_step_keys_match":true,"parameter_values_and_fd_steps_match":true} | {"parameter_step_keys_match":true,"parameter_values_and_fd_steps_match":true} | HARD | results/stage01c_autograd_regression.csv + stage_01c_autograd/results/native_autograd_fd.csv | — |

邻居索引选择仍是离散、非光滑过程；本报告不把连续 tensor value path
扩展解释为拓扑可微性。

## 7. 证据索引

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
| `06_experiments/stage_01c_operator_candidates/results/stage01c_gate_status.txt` | `b8ca179abb637e75affaf8010149468eca984e1d21524a9f68b5ed49f107c8d7` | 32 |
| `06_experiments/stage_01d_fixed_physics_tgv/configs/preregistered_primary_tgv.yml` | `7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0` | 11213 |
| `06_experiments/stage_01d_fixed_physics_tgv/generate_stage01d_reports.py` | `e1c284f1a09096d47c409b1e2c191962e0688ac63c717d7e71f31e77ac366f3d` | 90421 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/dynamic_autograd_fd.csv` | `b697887261913b7b6d54ddfb27be7ef8719af7639f059989086b559637a8e431` | 8280 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/run_summary.csv` | `74f96bd7d9bbb3cecb164221a6ac8d1c8eb9502b06aefe670bb530f41df47a06` | 6532 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01c_sha256_manifest.csv` | `46a66c51863c10eb07db1c57401ee8008a5335e20cd54bf132cb5d9337bcdcc2` | 10979 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_gate_evidence.csv` | `fbcb0a2e0b8d0f97c39da2c2b2d1fec5e918e5ea046cf7548f19670b48e411a3` | 17101 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt` | `7bd1685c7a729a27af2b89caf66a1a5fbaecaa951ae47f26406b58636df0dc1e` | 8 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/smoke_n16_increasing_neighbor_n16_h4p00_dt0p00100000_tf0p010_cs20p0_regular_s0.csv` | `c9ed548fd816ee96960ed0e6029347de2f18a893f9e2e0f33492723ce27d486c` | 23599 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0.csv` | `3a14895da85a32dc70bfd1a6c1738b484a3cea20038d2a5ac1bc4fa86f9cbb61` | 12036 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/zero_flow_constant_neighbor_n16_h4p00_dt0p00100000_tf0p100_cs20p0_regular_s0.csv` | `e0ac5be242e2ce6c5554c9145f89dac56e51f70fe323913b7cc6f9bd5ee81c9d` | 182665 |
