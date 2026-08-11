# Stage 02D — R2 Reference Sensitivity Report

机器预算见 `../04_target_attribution/reference_sensitivity/reference_sensitivity_budget.json`。

## 1. Norm definitions

对向量场差值 \(d_i\)，本报告使用

\[
L_2=\sqrt{\frac{1}{N}\sum_i\|d_i\|_2^2},
\qquad
L_\infty=\max_i\|d_i\|_2,
\]

相对量为 \(L_2(d)/L_2(a_{ref}^{primary})\)。没有自动选择或追溯拟合 smallness threshold。

## 2. DOP853 primary vs sensitivity

两个 DOP853 容差层在本次极短 audit horizon 上，对6个 sample times 得到：

- \(\|a_{ref}^{primary}-a_{ref}^{sensitivity}\|_{L2}=0\)；
- \(\|a_{ref}^{primary}-a_{ref}^{sensitivity}\|_{L\infty}=0\)；
- relative L2 = 0。

这是本批次 float64 输出的逐位观测，不是一般 DOP853 误差为零的声明，也不产生新的阈值。RK2 state 与
DOP853 primary state 经 dense RHS 后的 acceleration Linf 在 `t=0` 为0，在 `t=0.002` 为约
`2.98846e-7`（regular N6）和 `1.31365e-6 m s^-2`（jitter N8）。

## 3. Can time contamination be declared negligible?

不能。4个 topology-qualified sample 的 \(\Delta a\) 本身为零，因此

\[
\|\Delta a_{time}\|/\|\Delta a\|
\]

未定义，不能据 DOP853 sensitivity 为零就宣布 \(\Delta a_{time}\ll\Delta a\)。两个非零 target 来自预注册
duplicate-edge failure，已经 rejected；其比值不具有 discretization attribution 意义。

## 4. Reference uncertainty budget

- dense forward/reverse Linf component difference：`1.11e-16`–`2.22e-16 m s^-2`；
- frozen float64 audit bound：`1.1369e-12`–`1.1937e-12 m s^-2`，6/6 PASS；
- DOP853 primary/sensitivity：本批次观测为0；
- sparse/dense assembly sensitivity：正控制为0；负控制 vector Linf 约0.09163–0.09211 m/s²并由 topology
  failure 解释。

各项保持分列，`single_total_uncertainty_permitted=false`。Uncertainty 不用于 noise augmentation，也没有被
注入或扰动样本。
