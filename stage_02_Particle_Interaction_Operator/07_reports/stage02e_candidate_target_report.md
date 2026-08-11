# Stage 02E — Candidate Target Audit Report

Candidate pool 见 `../04_target_attribution/target_construction/candidate_target_pool.json`；归因结果见
`../04_target_attribution/qualification/attribution_results_stage02e.json`。

## 1. Non-zero audit

8/8 candidates 均满足 \(\|\Delta a\|_{L\infty}>0\)，没有人工删除小 target：

- L2 range：`4.0596e-8`–`3.2535e-7 m s^-2`；
- Linf range：`5.6107e-8`–`4.3813e-7 m s^-2`；
- 每条记录保存完整 `delta_a`、per-particle magnitude、quantiles、graph total variation、reverse-null ratio 和
  Fourier signature。

## 2. Reference qualification

8/8 R2 records 的 same state、same configuration、same timestamp、graph contract 和 uncertainty availability
均为 PASS，reference identity 固定为 `stage02e_r2_dop853_five_point_derivative_v1`。该 PASS 只允许 R2 audit
使用，`training_reference_permitted=false`。

## 3. Algebraic attribution

每个 target 被显式分解为

\[
\Delta a=(a_{dense}^{instant}-a_{SPH}^{sparse})
+(a_{ref}^{5pt}-a_{dense}^{instant})+r_{closure}.
\]

7个 cases 的 assembly L2 为0；compressive case 为 `5.82e-18 m s^-2`。Temporal-reference component 对 target
的 L2 fraction 为1或 `0.999999999989`，closure 为 roundoff。五点 window sensitivity 约
`3.81e-8`–`3.05e-7 m s^-2`，与 target 同量级；DOP853 solver-tolerance sensitivity 本批次为0。

因此非零 target 被归因为 temporal/reference construction，而不是 spatial discretization。

## 4. Six-component result

所有8条 categorical attribution vectors 均包含：spatial consistency、resolution trend、support consistency、
time contamination、reference sensitivity 和 model-form compatibility。没有任何记录达到6/6 PASS：

- `candidate_discretization_target=0`；
- `diagnostic=8`；
- `rejected=0`。

这8条是 audit candidates，不是 training dataset。
