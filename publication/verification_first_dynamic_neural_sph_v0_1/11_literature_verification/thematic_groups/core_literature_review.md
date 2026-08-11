# Core literature review

截至2026-08-05共核验87篇，核心引用40篇。以下比较只使用verified题录；强方法陈述优先来自全文。

## T1 直接SPH/ML工作

Neural SPH把SPH压力、黏性和外力分量加入完全学习GNN的训练与rollout [V003]；Woodward等参数化SPH核与项用于湍流降阶模型 [V001]；JAX-SPH与diffSPH已分别建立可微SPH、AD/FD或长期梯度传播及solver-in-the-loop [V002,V004]。因此，本稿的空间不在‘首次learnable/differentiable SPH’，而在冻结资格合同及完整负证据。

## T2 学习型粒子动力学

GNS、continuous convolutions和DPI-Net均直接学习粒子更新并进行自回归或任务rollout [V010,V011,V013]；LagrangeBench提供SPH数据、多个GNN基线与物理指标 [V024]。这些工作是fully learned particle simulator，而非保留SPH推进的additive correction。

## T3 守恒与等变

DMCF用反对称连续卷积硬保证线动量 [V022]；DYNAMI-CAL GRAPHNET同时硬编码线/角动量交换 [V028]；EGNN/SEGNN编码几何等变但不自动保证守恒 [V017,V023]。

## T4 可微求解器与梯度核验

Solver-in-the-loop已建立多步可微PDE corrector训练 [V016]；AD-CFD与tangent/adjoint checking形成导数核验传统 [V005,V007,V008]；JAX-SPH是本稿多步AD/FD最直接的部分先例 [V002]。

## T5 动态图与事件

核验集合包含每步近邻重建、动态粒子图和可微物理，但没有核实到与本项目相同的SPH cutoff birth/death、fixed-side gradients和piecewise-smooth资格组合。该结论是有界空缺，不是全局首次性声明。

## T6 Scientific ML V&V

SciML V&V框架要求区分verification、calibration、validation、prediction domain与UQ [V020,V029]；REFORMS支持透明主张和复现 [V025]。这些文献支持本稿方法定位，但不验证具体SPH合同。

## T7 SPH verification

SPH grand challenges、一致性、收敛、WCSPH时间步与MMS文献说明普通benchmark不应自动称为validation [V042,V056,V058,V076,V018,V035]。
