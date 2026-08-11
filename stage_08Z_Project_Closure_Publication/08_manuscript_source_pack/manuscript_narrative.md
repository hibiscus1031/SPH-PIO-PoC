# 中文研究叙事

本项目研究的核心不是获得一条表现优异的 SPH–Transformer 曲线，而是回答：在信任粒子求解器中的保守神经修正之前，应当逐层验证什么？项目从 SPH 方程、离散算子、reference 角色和有限分辨率边界开始，将结构正确性、目标可表示性、梯度有效性、实际优化器更新、正式训练达标和验证支持区分为不同资格层。

早期静态 pair-force 路线证明，满足互易反对称和守恒合同并不保证训练拟合成功。动态 RK2 混合实现随后通过零修正等价、结构和一步梯度检查，但完整多步 AD/FD 资格化失败。Stage04 进一步表明，即使神经修正 Jacobian 非零，raw next-state loss 仍可能产生难以检测的参数训练信号。

Stage05 因而建立以 D0 accepted-state defect 为中心、带冻结尺度和保守分解的目标；Stage06 的 actual AdamW update 资格化说明该目标可产生可识别的更新动力学。然而九条正式训练 run 均未达到冻结的全局门。Stage07 增加公式异质性后再次执行九条训练 run，仍未通过，并将主要失败归因为 HET_S2_02 的 held-out support gap。

Stage08 以前瞻性四层 coverage 设计替代 hash 内部分配。192/192 候选通过基础资格化，HET_S2_02 descriptor distance 从 6.5115 降到 1.8607，但 target-PCA residual 为 3.5113，高于 1.5385 门限，且 fresh-validation 正式封闭为 0/4。由此，项目支持“descriptor coverage 不等于 correction-target manifold coverage”，但不支持成功训练求解器、Transformer 优越性或 sealed-test 性能主张。

论文应定位为 verification-first、qualification-first、failure-driven computational methodology article。失败路线不是调参日志，而是用于揭示资格层之间不可替代的因果边界。
