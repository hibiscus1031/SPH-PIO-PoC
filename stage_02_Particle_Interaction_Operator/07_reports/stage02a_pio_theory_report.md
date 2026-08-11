# Stage 02A — PIO Theory Qualification Report

**冻结日期：** 2026-08-04  
**范围：** PIO 数学定义和物理约束冻结  
**执行声明：** 本阶段未实施模型、Transformer、神经网络、训练、数据集/标签生成、参数调节或 benchmark。

## 1. PIO motivation

Stage 01 已提供可审计的 SPH RHS、守恒/拓扑审计、MMS/半离散 reference 与独立 benchmark 框架，也同时
保留了 `V2_QUALIFICATION_FAIL`。PIO 的研究动机不是替代该物理基线，而是在相同粒子状态和冻结合同上，
研究能否估计可归因的粒子离散残差。增量形式保留 baseline 的物理解释、失败审计与可关闭回退路径。

## 2. Problem definition

冻结 baseline 与 reference：

\[
a_{\mathrm{SPH},i}=\mathcal A_{\mathrm{SPH}}(\mathcal S,\mathcal G)_i,
\qquad
a_{\mathrm{ref},i}=\mathcal A_{\mathrm{ref}}(\mathcal S;i).
\]

唯一 PIO 目标和校正定义为

\[
\boxed{\Delta a_i=a_{\mathrm{ref},i}-a_{\mathrm{SPH},i}},\qquad
\boxed{a_{\mathrm{corr},i}=a_{\mathrm{SPH},i}+\widehat{\Delta a}_i}.
\]

PIO 不得直接预测 \(a_{\mathrm{corr}}\)，不得替代 EOS、pressure、viscosity、density summation、kernel /
neighbor search 或 time integration。完整定义见
`../02_operator_design/theory/pio_mathematical_definition.md`。

## 3. Baseline / reference hierarchy

Reference 冻结为四类：R1 continuum-compatible analytic/MMS 用于 verification；R2 semidiscrete-qualified
high-order temporal reference 用于隔离时间/状态误差；R3 independent shear/acoustic benchmark 用于
validation 且默认不训练；RX model-form-misaligned 只用于诊断。R1 仍必须检查 WCSPH model-form alignment，
解析性不自动赋予标签资格。详细决策见 `stage02a_reference_hierarchy.md`。

## 4. Learning target 与 zero-correction fallback

目标只允许是 reference 与 baseline 在同一合格状态上的加速度残差，而且仅允许其中已归因的 discretization
component。若 \(\widehat{\Delta a}=0\)，则逐粒子严格有

\[
a_{\mathrm{corr}}=a_{\mathrm{SPH}},
\]

从而恢复冻结 baseline。这是代数恒等式和未来硬测试，不是统计性能声明。

## 5. Pair-force formulation

Level 1 node residual

\[
\widehat{\Delta a}_i=f_\theta(s_i,\mathcal N(i))
\]

仅作为理论 baseline。优先的 Level 2 定义为

\[
\Delta F_{ji}=-\Delta F_{ij},\qquad
\widehat{\Delta a}_i=\frac{1}{m_i}\sum_j\Delta F_{ij}.
\]

它在 reciprocal 合格图上从构造保证 correction total force 为零。图必须沿用 baseline minimum-image、support
与 topology contract，不能由 PIO 静默修改。

## 6. Conservation constraints

Pair antisymmetry 给出

\[
\sum_i m_i\widehat{\Delta a}_i=0,
\]

即封闭周期系统的线动量硬合同。它不自动保证角动量、能量或黏性耗散：角动量还要求中心力/零 pair torque，
能量还要求修正功率的独立符号条件。未来必须分开报告 total force、pair residual、torque 与 pressure/viscous
power。详见 `stage02a_conservation_contract.md`。

## 7. Equivariance constraints

冻结六项合同：particle permutation equivariance、translation invariance、periodic minimum-image consistency、
rotation equivariance、pair exchange symmetry、zero correction fallback。旋转状态时需同时旋转周期晶格；固定
矩形盒只要求其晶格点群旋转。动态图允许 reciprocal cutoff crossing，不要求 edge identity 恒定，但必须记录
graph hash、reciprocal status 和 topology defects。详见 `stage02a_equivariance_contract.md`。

## 8. Label eligibility

每个未来候选标签必须具有 reference class/uncertainty、state/config/neighbor graph hash、failure flags、
topology/resource/determinism status 和 model-form compatibility，并补充 provenance、误差归因、独立性与
machine-readable verdict。只有所有硬门通过且目标被归因为 discretization component 时，才可标记为未来训练
候选；R3 默认验证隔离，RX 禁止。详见 `stage02a_label_eligibility.md` 和
`../02_operator_design/validation_contract/label_eligibility_schema.md`。

## 9. Error decomposition

冻结账本为

\[
e_{\mathrm{total}}=e_{\mathrm{space}}+e_{\mathrm{time}}+e_{\mathrm{reference}}
+e_{\mathrm{forcing}}+e_{\mathrm{model\_form}}+e_{\mathrm{cross}}.
\]

该式是归因要求，不声称所有项天然可观测或独立。PIO 只能针对可归因 discretization component；禁止把
continuum–SPH 全差异直接定义为 discretization error。无法隔离的交叉项使标签降级为 unresolved/diagnostic。

## 10. Attention relationship

SPH kernel 是 fixed physical interaction weighting；attention 若未来采用，是 learned interaction weighting；
PIO 是 learned correction over a validated physical interaction。Attention 不替换 kernel，softmax 归一也不等于
核矩、partition of unity、pair antisymmetry 或守恒。本文只冻结此理论映射，不实现 attention。详见
`../02_operator_design/theory/attention_kernel_relationship.md`。

## 11. Open problems

未解决问题包括：node 与 pair 表达能力；目标总力不可守恒分量的处置；中心/非中心黏性修正的 torque–power
折中；cutoff crossing 的稳定性；R1 forcing 与 R2 state alignment 的可识别性；uncertainty floor；周期域角动量
convention；pressure/viscous 分通道；correction limiter；reference-source leakage；独立 benchmark 的保留范围。
完整清单见 `stage02a_open_questions.md`。

## 12. Future Stage 02B requirements

Stage 02B 必须在任何数据执行前冻结 reference-to-target 路径、model-form/forcing/state alignment、reference
uncertainty 门、hash serialization、topology/resource/determinism 门、防泄漏 family split、unseen
resolution/disorder、独立 benchmark、评价范数/短 rollout/守恒与 metamorphic 决策表，并建立独立的数据生成
授权门。Stage 02A 完成不自动授权 Stage 02B 执行、模型实现或训练。

## 13. Stage 01 boundary

可迁移 validated SPH RHS、conservation/topology audit、MMS framework、reference hierarchy 与资源/确定性方法；
不可迁移 V2 PASS、learned correction effectiveness 或 generalization claim。Stage 01G
`V2_QUALIFICATION_FAIL`、shear finite-resolution dominant 诊断和“未确认 viscosity operator form failure”均保持
原义。详见 `stage02a_stage01_boundary.md`。

## 14. Qualification checklist

- [x] mathematical definition complete；
- [x] reference hierarchy complete；
- [x] conservation contract complete；
- [x] symmetry contract complete；
- [x] label eligibility complete；
- [x] error decomposition and validation contract complete；
- [x] no training；
- [x] no model implementation；
- [x] no dataset generation；
- [x] Stage 01 unchanged。

## 15. 唯一状态

`PIO_THEORY_QUALIFICATION_COMPLETE`

该状态只表示 Stage 02A 的数学与物理合同已冻结，不是 model performance、training result、V2 upgrade 或
Stage 03 授权。
