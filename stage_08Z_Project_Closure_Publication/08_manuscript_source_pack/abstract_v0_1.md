# Abstract v0.1

## 中文

我们提出并执行一条面向 SPH 保守神经修正的 qualification-first 证据链，将求解器验证、reference 角色、互易反对称结构、accepted-state 离散缺陷、梯度、实际优化器更新、正式训练和支持区覆盖分离为不同资格层。结构和实际 AdamW 更新动力学获得资格，但两轮各九条正式训练 run 均未满足冻结的全局标准。系统化 Stage08 coverage 将关键 held-out lineage 的 descriptor distance 从 6.5115 降至 1.8607，却未使其 target-PCA residual 低于 1.5385 门限，fresh-validation 封闭为 0/4。结果表明，结构正确、局部可训练和 descriptor 支持均不能替代 target-manifold 与全局训练资格。项目未建立合格的 SPH–Transformer 求解器；其贡献是可审计的资格阶梯和失败驱动方法学。

## English scientific source

We develop and execute a qualification-first evidence chain for conservative neural corrections in smoothed particle hydrodynamics, separating solver verification, reference roles, reciprocal antisymmetric structure, accepted-state discrete defects, gradients, actual optimizer updates, formal training, and support coverage. Structural contracts and actual AdamW update dynamics were qualified, yet two nine-run formal campaigns failed their frozen global criteria. A prospective systematic-coverage experiment reduced the descriptor distance of a critical held-out lineage from 6.5115 to 1.8607, while its target-PCA residual remained 3.5113 against a 1.5385 threshold and formal fresh-validation closure remained 0/4. These results show that structural correctness, local trainability, and descriptor support cannot substitute for target-manifold and global-training qualification. The study does not establish a qualified SPH–Transformer solver; it provides an auditable qualification ladder and failure-driven computational methodology.
