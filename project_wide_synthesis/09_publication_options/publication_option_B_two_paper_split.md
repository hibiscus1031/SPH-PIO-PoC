# Option B：拆分两篇

## Paper 1：Stage 00–03 verification-first方法论文

- Research question：保守dynamic neural-SPH在训练前如何通过reference、结构、零修正、多步梯度和拓扑事件资格链？
- Contribution：失败保留的V&V链、static learnability负结果、360-probe梯度边界、拓扑分量资格。
- Figures/Tables：pipeline、timeline、failure tree、evidence hierarchy、AD/FD矩阵、topology；状态账本与claim boundary。
- Title candidates：*Verification-first qualification of conservative dynamic neural–SPH solvers*；*From reference qualification to multistep gradient limits in neural SPH*。
- Target level：[PUBLICATION_RECOMMENDATION] CMAME/Journal of Computational Physics层级需突出一般方法；若一般性不足则选择更专门的计算力学/数值方法期刊。
- Fatal weakness：单一项目/问题范围，且没有训练性能；必须把论文定位为资格方法与负结果，而非solver success。

## Paper 2：Stage 04 dynamic training and performance

- Research question：local-causal dynamic training是否在合格梯度、rollout、独立验证和成本门下优于D0/D1/D2？
- Contribution：只能来自Stage04新证据；Stage00–03仅作共享背景。
- Required additions：合格训练、autonomous rollout、refinement、independent validation、cost与失败证据。
- Fatal weakness：若只有短窗fit或单case improvement，不足以形成完整性能论文。
