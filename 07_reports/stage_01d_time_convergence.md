# Stage 01D TGV 时间收敛报告

日期：2026-07-31

执行状态：**NOT_RUN**。run summary 中观察到 0/4 个预期轨迹。

未执行或未完成原因（原样来自证据）：`time phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0`。

## 1. 固定配置

`N=32`，
`H/dx=5.0`，
`t_final=0.2`，
时间步为
`[0.001, 0.0005, 0.00025, 0.000125]`。

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

## 2. 解析终点误差

_无记录。_

## 3. 21 个共同物理时刻的连续 dt 自收敛

_无记录。_

完整 21 点逐时刻差保存在 evaluator CSV，不在 Markdown 中删减或重新拟合。
若解析误差进入平台，报告只保留 `time_platform_detected` 的机器记录，不强制
宣称二阶。

## 4. 轨迹终点与运行诊断

_无记录。_

## 5. 时间 gate

| gate | check | passed | observed | threshold | severity | source | detail |
|---|---|---|---|---|---|---|---|
| T | four_time_trajectories_finite | False | NOT_RUN | True | NOT_RUN | results/time_convergence_metrics.csv | time phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| T | analytic_endpoint_credible_decrease | False | NOT_RUN | at least one selected finest/coarsest ratio <= None | NOT_RUN | results/time_convergence_metrics.csv | time phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| T | velocity_self_convergence_credible_decrease | False | NOT_RUN | <= None | NOT_RUN | results/time_convergence_metrics.csv | time phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |
| T | analytic_or_self_time_trend | False | NOT_RUN | analytic OR self trend passes | NOT_RUN | results/time_convergence_metrics.csv | time phase blocked by a prior preregistered hard gate; prior_failed_run_ids=smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0 |

## 6. 证据索引

| evidence path | SHA-256 | bytes |
|---|---|---|
| `06_experiments/stage_01d_fixed_physics_tgv/configs/preregistered_primary_tgv.yml` | `7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0` | 11213 |
| `06_experiments/stage_01d_fixed_physics_tgv/generate_stage01d_reports.py` | `e1c284f1a09096d47c409b1e2c191962e0688ac63c717d7e71f31e77ac366f3d` | 90421 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/run_summary.csv` | `74f96bd7d9bbb3cecb164221a6ac8d1c8eb9502b06aefe670bb530f41df47a06` | 6532 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_gate_evidence.csv` | `fbcb0a2e0b8d0f97c39da2c2b2d1fec5e918e5ea046cf7548f19670b48e411a3` | 17101 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt` | `7bd1685c7a729a27af2b89caf66a1a5fbaecaa951ae47f26406b58636df0dc1e` | 8 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/time_convergence_metrics.csv` | `31ff2fc54e03cdd550457cf3818db25c2933642bde561e7cd2e646092589e94d` | 329 |
