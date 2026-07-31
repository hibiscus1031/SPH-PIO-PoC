# Stage 01D 动态支撑族比较

日期：2026-07-31

执行状态：**NOT_RUN**。run summary 中观察到 0/3 个预期轨迹。

未执行或未完成原因（原样来自证据）：`space_and_support phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0`。

## 1. 比较设计

相同 fixed physics、规则布局、`dt=0.000125`、
`t_final=0.2`。
constant-neighbor 使用 `H/dx=4`；increasing-neighbor 使用预登记的
`4.0, 4.5, 5.0`。配置明确禁止预设有限分辨率赢家。

## 2. 三个主误差及空间趋势

_无可显示字段。_

## 3. 轨迹误差、成本与邻居数

_无记录。_

_无记录。_

## 4. 机器 gate

| gate | check | passed | observed | threshold | severity | source | detail |
|---|---|---|---|---|---|---|---|
| S | both_support_families_complete | False | NOT_RUN | 3 regular trajectories per support family | NOT_RUN | results/space_convergence_metrics.csv | space_and_support phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |

表格用于判断静态 truncation–quadrature tradeoff 是否出现在完整动态中；
生成器不从缺失、非单调或失败轨迹补造优胜结论。

## 5. 证据索引

| evidence path | SHA-256 | bytes |
|---|---|---|
| `06_experiments/stage_01d_fixed_physics_tgv/configs/preregistered_primary_tgv.yml` | `7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0` | 11213 |
| `06_experiments/stage_01d_fixed_physics_tgv/generate_stage01d_reports.py` | `e1c284f1a09096d47c409b1e2c191962e0688ac63c717d7e71f31e77ac366f3d` | 90421 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/run_summary.csv` | `74f96bd7d9bbb3cecb164221a6ac8d1c8eb9502b06aefe670bb530f41df47a06` | 6532 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/space_convergence_metrics.csv` | `d4c27789ac7b405c310e0a94a27bed728c7f6c52514ce80a9e301d35075eea09` | 355 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_gate_evidence.csv` | `fbcb0a2e0b8d0f97c39da2c2b2d1fec5e918e5ea046cf7548f19670b48e411a3` | 17101 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt` | `7bd1685c7a729a27af2b89caf66a1a5fbaecaa951ae47f26406b58636df0dc1e` | 8 |
