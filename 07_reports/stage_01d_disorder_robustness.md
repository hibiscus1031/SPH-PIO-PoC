# Stage 01D 动态粒子无序稳健性

日期：2026-07-31

执行状态：**NOT_RUN**。run summary 中观察到 0/7 个预期轨迹。

未执行或未完成原因（原样来自证据）：`disorder phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0`。

## 1. 预登记布局和种子

`N=32`、`dt=0.00025`、
`H/dx=5.0`、`t_final=0.1`。
种子映射规则：Stage 01C seed list positions 1-3 map to 5% jitter and positions 4-6 map to 10% jitter。

| layout | seeds |
|---|---|
| regular | `[0]` |
| jitter_05 | `[20261001, 20261019, 20261037]` |
| jitter_10 | `[20261061, 20261079, 20261103]` |

## 2. evaluator 布局汇总

_无可显示字段。_

## 3. 逐轨迹最后可用样本

_无记录。_

## 4. 失败轨迹

_无记录。_

## 5. 动态无序 gate

| gate | check | passed | observed | threshold | severity | source | detail |
|---|---|---|---|---|---|---|---|
| D | regular_disorder_control | False | NOT_RUN | True | NOT_RUN | results/disorder_summary.csv | disorder phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| D | jitter_05_disorder_control | False | NOT_RUN | True | NOT_RUN | results/disorder_summary.csv | disorder phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| D | jitter_10_velocity_error_multiplier | False | NOT_RUN | <= None | NOT_RUN | results/disorder_summary.csv | disorder phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| D | all_disorder_layouts_robust | False | NOT_RUN | all pre-registered runs pass core and clustering gates | NOT_RUN | results/disorder_summary.csv | disorder phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| D | conditional_disorder_regular_and_jitter05_only | False | NOT_RUN | PASS if all layouts pass; CONDITIONAL only if regular and 5% pass while 10% fails with sampled failure evidence | NOT_RUN | results/disorder_summary.csv | disorder phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |

本部分只描述预登记的 7 个轨迹，不把三个种子解释为完整随机不确定性。

## 6. 证据索引

| evidence path | SHA-256 | bytes |
|---|---|---|
| `06_experiments/stage_01d_fixed_physics_tgv/configs/preregistered_primary_tgv.yml` | `7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0` | 11213 |
| `06_experiments/stage_01d_fixed_physics_tgv/generate_stage01d_reports.py` | `e1c284f1a09096d47c409b1e2c191962e0688ac63c717d7e71f31e77ac366f3d` | 90421 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/disorder_summary.csv` | `c47df9515fc73976f30339db3e21fade00ea54a6063266d630994122431ff21c` | 337 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/run_summary.csv` | `74f96bd7d9bbb3cecb164221a6ac8d1c8eb9502b06aefe670bb530f41df47a06` | 6532 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_gate_evidence.csv` | `fbcb0a2e0b8d0f97c39da2c2b2d1fec5e918e5ea046cf7548f19670b48e411a3` | 17101 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt` | `7bd1685c7a729a27af2b89caf66a1a5fbaecaa951ae47f26406b58636df0dc1e` | 8 |
