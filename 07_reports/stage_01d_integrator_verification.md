# Stage 01D 时间积分器验证

日期：2026-07-31

本报告使用两个独立 ODE 的实际 CSV；没有用求解器名称替代阶数证据。

## 1. 预登记问题

- 标量：`dy/dt = -1.3*y`；
- 耦合：`y0' = y1; y1' = -2*y0 - 0.4*y1`；
- 时间步：`[0.1, 0.05, 0.025, 0.0125]`。

## 2. 原始误差序列

| problem | method | dt | steps | error L2 | pair observed order | git hash | config SHA-256 |
|---|---|---|---|---|---|---|---|
| scalar_decay | explicit_midpoint_rk2 | 0.1 | 10 | 0.001102467 | — | 3290b65837805ae5aa15f98580ffcd7e002161ba | 7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0 |
| scalar_decay | explicit_midpoint_rk2 | 0.05 | 20 | 2.620840e-04 | 2.072635 | 3290b65837805ae5aa15f98580ffcd7e002161ba | 7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0 |
| scalar_decay | explicit_midpoint_rk2 | 0.025 | 40 | 6.391756e-05 | 2.035745 | 3290b65837805ae5aa15f98580ffcd7e002161ba | 7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0 |
| scalar_decay | explicit_midpoint_rk2 | 0.0125 | 80 | 1.578423e-05 | 2.017728 | 3290b65837805ae5aa15f98580ffcd7e002161ba | 7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0 |
| coupled_damped_oscillator | explicit_midpoint_rk2 | 0.1 | 10 | 0.004042773 | — | 3290b65837805ae5aa15f98580ffcd7e002161ba | 7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0 |
| coupled_damped_oscillator | explicit_midpoint_rk2 | 0.05 | 20 | 0.001019055 | 1.988113 | 3290b65837805ae5aa15f98580ffcd7e002161ba | 7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0 |
| coupled_damped_oscillator | explicit_midpoint_rk2 | 0.025 | 40 | 2.559582e-04 | 1.993252 | 3290b65837805ae5aa15f98580ffcd7e002161ba | 7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0 |
| coupled_damped_oscillator | explicit_midpoint_rk2 | 0.0125 | 80 | 6.414677e-05 | 1.996459 | 3290b65837805ae5aa15f98580ffcd7e002161ba | 7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0 |

## 3. evaluator 阶数门

| problem | all dt present | errors decrease | fitted order | fitted minimum | finest pair order | finest minimum | pass | source |
|---|---|---|---|---|---|---|---|---|
| scalar_decay | True | True | 2.041407 | 1.8 | 2.017728 | 1.75 | True | 06_experiments/stage_01d_integrator_verification/results/integrator_verification.csv |
| coupled_damped_oscillator | True | True | 1.992673 | 1.8 | 1.996459 | 1.75 | True | 06_experiments/stage_01d_integrator_verification/results/integrator_verification.csv |

| gate | check | passed | observed | threshold | severity | source | detail |
|---|---|---|---|---|---|---|---|
| I | scalar_decay_second_order | True | {"decreases":true,"finest_pair_order":2.017727908586886,"fitted_order":2.0414066768743058} | {"finest_pair_order_minimum":1.75,"fitted_order_minimum":1.8} | HARD | 06_experiments/stage_01d_integrator_verification/results/integrator_verification.csv | — |
| I | coupled_damped_oscillator_second_order | True | {"decreases":true,"finest_pair_order":1.9964594041753698,"fitted_order":1.992672681349704} | {"finest_pair_order_minimum":1.75,"fitted_order_minimum":1.8} | HARD | 06_experiments/stage_01d_integrator_verification/results/integrator_verification.csv | — |
| I | both_ode_integrator_gates | True | 2/2 | 2/2 | HARD | 06_experiments/stage_01d_integrator_verification/results/integrator_verification.csv | — |

只有 `both_ode_integrator_gates` 的机器记录通过，TGV 前置积分器门才可视为
通过；本报告不另行放宽 fitted-order 或 finest-pair 阈值。

## 4. 证据索引

| evidence path | SHA-256 | bytes |
|---|---|---|
| `06_experiments/stage_01d_fixed_physics_tgv/configs/preregistered_primary_tgv.yml` | `7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0` | 11213 |
| `06_experiments/stage_01d_fixed_physics_tgv/generate_stage01d_reports.py` | `e1c284f1a09096d47c409b1e2c191962e0688ac63c717d7e71f31e77ac366f3d` | 90421 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/integrator_gate_evidence.csv` | `6df650601d9454f9268180c5c31c691c1a8c44c7b7f19084e168ba3a841fb1ad` | 622 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/run_summary.csv` | `74f96bd7d9bbb3cecb164221a6ac8d1c8eb9502b06aefe670bb530f41df47a06` | 6532 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_gate_evidence.csv` | `fbcb0a2e0b8d0f97c39da2c2b2d1fec5e918e5ea046cf7548f19670b48e411a3` | 17101 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt` | `7bd1685c7a729a27af2b89caf66a1a5fbaecaa951ae47f26406b58636df0dc1e` | 8 |
| `06_experiments/stage_01d_integrator_verification/results/integrator_verification.csv` | `dcfba86b69e6ff2fad4d9325d4b93a8b0916d3f4be3c7eca6fe530b96073217b` | 2118 |
