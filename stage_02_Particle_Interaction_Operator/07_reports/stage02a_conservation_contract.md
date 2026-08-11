# Stage 02A — Conservation Contract 报告

规范合同见 `../02_operator_design/constraints/pio_conservation_contract.md`。

## 冻结设计

Level 2 pair-force correction 是优先理论形式：

\[
\Delta F_{ji}=-\Delta F_{ij},\qquad
\widehat{\Delta a}_i=m_i^{-1}\sum_j\Delta F_{ij}.
\]

在封闭周期系统、完整 reciprocal graph 且每个无向 pair 恰计一次时，

\[
\sum_i m_i\widehat{\Delta a}_i
=\sum_{\{i,j\}}(\Delta F_{ij}+\Delta F_{ji})=0.
\]

因此线动量守恒由结构给出，而不是通过 loss 近似鼓励。Level 1 node residual 仅是 baseline，不自动获得该资格。

## 不扩大声明

- pair antisymmetry **不自动保证角动量守恒**；还需要中心力或等价 torque-free 条件；
- pair antisymmetry **不自动保证能量守恒、耗散或熵稳定**；
- 周期 torus 上的全局角动量需明确 unwrapped convention，未来首先报告局部 pair torque；
- 非中心黏性修正必须单独评价 torque 与功率，不能借 Stage 01H 声称黏性算子形式已失败；该失败并未确认。

修正瞬时功率冻结为

\[
P_{\mathrm{PIO}}=\sum_{\{i,j\}}(v_i-v_j)\cdot\Delta F_{ij},
\]

并要求未来按压力型、黏性型和总修正分项报告。

## 拓扑门

duplicate、nonreciprocal、strict-support omission、unexpected exterior edge 均为硬失败。reciprocal cutoff
crossing 合法，但同一状态的两个方向必须一致进入/退出。graph hash、reciprocal status 与 defects 是每个未来
样本的强制元数据。
