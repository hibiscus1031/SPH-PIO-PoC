# Stage 01D TGV 空间收敛报告

日期：2026-07-31

执行状态：**NOT_RUN**。run summary 中观察到 0/3 个预期轨迹。

未执行或未完成原因（原样来自证据）：`space_and_support phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0`。

## 1. 主路线

固定 `dt=0.000125`、
`t_final=0.2`。
主分辨率与支撑比来自
`space_convergence.resolutions_and_support_ratios`，没有根据结果改值。

_无记录。_

## 2. 终点误差与运行量

_无记录。_

## 3. 可选 N=48

**NOT_RUN（可选确认点）**。现有证据没有 N=48 轨迹；是否满足 N=32 的 RSS/预计时长门应以 gate 与 run summary 为准，报告不推断。

_无记录。_

## 4. Richardson/GCI 边界

本生成器不计算 Richardson 外推或 GCI。`gci_eligible` 仅转录 evaluator
对单调和近渐近条件的检查；任何 `gci_computed=True` 都必须同时有
`gci_eligible=True`，否则生成器拒绝报告。

## 5. 空间 gate

| gate | check | passed | observed | threshold | severity | source | detail |
|---|---|---|---|---|---|---|---|
| S | primary_selected_spatial_slopes_positive | False | NOT_RUN | all three fitted slopes > 0 | NOT_RUN | results/space_convergence_metrics.csv | space_and_support phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| S | primary_velocity_n32_over_n16 | False | NOT_RUN | <= None | NOT_RUN | results/space_convergence_metrics.csv | space_and_support phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| S | primary_space_gate | False | NOT_RUN | positive slopes and velocity N32/N16 gate | NOT_RUN | results/space_convergence_metrics.csv | space_and_support phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| S | conditional_time_pass_space_plateau | False | NOT_RUN | time complete/finite/credible; space complete; primary nonworsening plateau; support evidence complete | NOT_RUN | results/time_convergence_metrics.csv + results/space_convergence_metrics.csv | space_and_support phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| S | both_support_families_complete | False | NOT_RUN | 3 regular trajectories per support family | NOT_RUN | results/space_convergence_metrics.csv | space_and_support phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |

## 6. 证据索引

| evidence path | SHA-256 | bytes |
|---|---|---|
| `06_experiments/stage_01d_fixed_physics_tgv/configs/preregistered_primary_tgv.yml` | `7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0` | 11213 |
| `06_experiments/stage_01d_fixed_physics_tgv/generate_stage01d_reports.py` | `e1c284f1a09096d47c409b1e2c191962e0688ac63c717d7e71f31e77ac366f3d` | 90421 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/run_summary.csv` | `74f96bd7d9bbb3cecb164221a6ac8d1c8eb9502b06aefe670bb530f41df47a06` | 6532 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/space_convergence_metrics.csv` | `d4c27789ac7b405c310e0a94a27bed728c7f6c52514ce80a9e301d35075eea09` | 355 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_gate_evidence.csv` | `fbcb0a2e0b8d0f97c39da2c2b2d1fec5e918e5ea046cf7548f19670b48e411a3` | 17101 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt` | `7bd1685c7a729a27af2b89caf66a1a5fbaecaa951ae47f26406b58636df0dc1e` | 8 |
