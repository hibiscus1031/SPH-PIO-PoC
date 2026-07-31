# Stage 01D 弱可压模型形式评估

日期：2026-07-31

执行状态：**NOT_RUN**。run summary 中观察到 0/3 个预期轨迹。

未执行或未完成原因（原样来自证据）：`mach phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0`。

## 1. 设计

规则布局 `N=32`、
`dt=0.00025`、
`H/dx=5.0`、
`t_final=0.1`。
预登记 `c_s=[10.0, 20.0, 40.0]`
与名义 Mach
`[0.1, 0.05, 0.025]`。

## 2. 误差、密度、压力、稳定性诊断和成本

_无可显示字段。_

`acoustic_cfl` 是预登记的 time-step stability diagnostic。配置没有登记一个
把它直接变成“稳定余量通过线”的额外阈值，因此报告不事后发明阈值。增大
`c_s` 的 wall time、peak RSS 和 acoustic CFL 均保留在表中。

## 3. 逐轨迹最后可用样本

_无记录。_

## 4. 模型形式 gate

| gate | check | passed | observed | threshold | severity | source | detail |
|---|---|---|---|---|---|---|---|
| M | three_mach_runs_quantified | False | NOT_RUN | all c_s={10,20,40} finite with error/density/cost evidence | NOT_RUN | results/mach_summary.csv | mach phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| M | conditional_quantified_model_form_error_dominant | False | NOT_RUN | three complete/core-passing Mach runs and a strict velocity-error decrease as Mach decreases | NOT_RUN | results/mach_summary.csv | mach phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |

模型形式结论只转录 evaluator 的三点趋势与 classification；如果速度误差不随
Mach 降低而改善，报告不得把主要误差归给弱可压模型形式。

## 5. 证据索引

| evidence path | SHA-256 | bytes |
|---|---|---|
| `06_experiments/stage_01d_fixed_physics_tgv/configs/preregistered_primary_tgv.yml` | `7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0` | 11213 |
| `06_experiments/stage_01d_fixed_physics_tgv/generate_stage01d_reports.py` | `e1c284f1a09096d47c409b1e2c191962e0688ac63c717d7e71f31e77ac366f3d` | 90421 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/mach_summary.csv` | `e72883fcc5dee437e68d6e38bed78574e76cf6d44c0a66d1bddfb291cb165027` | 329 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/run_summary.csv` | `74f96bd7d9bbb3cecb164221a6ac8d1c8eb9502b06aefe670bb530f41df47a06` | 6532 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_gate_evidence.csv` | `fbcb0a2e0b8d0f97c39da2c2b2d1fec5e918e5ea046cf7548f19670b48e411a3` | 17101 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt` | `7bd1685c7a729a27af2b89caf66a1a5fbaecaa951ae47f26406b58636df0dc1e` | 8 |
