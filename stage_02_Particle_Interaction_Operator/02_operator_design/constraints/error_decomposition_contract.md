# PIO 误差分解合同

## 1. 冻结分解

对同一可比观测量，误差账本必须至少写为

\[
e_{\mathrm{total}}=e_{\mathrm{space}}+e_{\mathrm{time}}+e_{\mathrm{reference}}
+e_{\mathrm{forcing}}+e_{\mathrm{model\_form}}+e_{\mathrm{cross}}.
\]

这是归因合同而非声称各项天然可加、可观测或统计独立。\(e_{\mathrm{cross}}\) 包含状态漂移、空间—时间耦合、
forcing—离散耦合及参考插值等不能唯一归入单项的影响。所有项必须共享明确的范数、状态和比较时刻。

## 2. PIO 可学习目标

PIO target 只能对应已被证据归因为粒子/空间离散的分量 \(e_{\mathrm{disc}}^{\mathrm{attr}}\)。候选差值

\[
\Delta a=a_{\mathrm{ref}}-a_{\mathrm{SPH}}
\]

只有在以下条件满足时才可解释为该目标：

1. continuous model 与冻结 WCSPH/EOS/forcing 合同相容；
2. baseline 与 reference 在同一粒子状态上评价，或状态对齐误差有界；
3. 时间误差已通过 qualified temporal/semidiscrete reference 隔离或有界；
4. reference uncertainty 明确且通过标签门；
5. forcing discretization 已单独核对；
6. 剩余交叉项相对目标足够小，且判据在 Stage 02B 预先冻结。

## 3. 明确禁止

- 禁止把所有 continuum–SPH 差异统称为 discretization error；
- 禁止以更小时间步得到的 trajectory 差异直接冒充瞬时空间加速度标签；
- 禁止把 R2 对时间误差的隔离结果自动改称空间修正；
- 禁止让 RX model-form-misaligned reference 进入训练资格；
- 禁止把 reference uncertainty 吸收到模型 loss 或 residual 后不再报告；
- 禁止在尚未证明可分解时用单一 GCI 汇总所有误差；应保留 `GCI not justified`。

## 4. 资格记录

每个未来候选标签必须分别记录上述误差项的状态：`isolated`、`bounded`、`not_applicable`、
`unresolved` 或 `failed`，以及证据引用。任一非目标项为 `unresolved/failed` 时，不得给出
`eligible_for_training`；它仍可保留为诊断记录。
