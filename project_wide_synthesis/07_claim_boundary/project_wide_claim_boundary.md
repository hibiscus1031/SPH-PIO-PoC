# 全项目主张边界

| ID | 分类 | 允许措辞 | 禁止措辞 | 限制 | 稿件角色 |
|---|---|---|---|---|---|
| C01 | SUPPORTED | Stage03C实现已验证。 | 动态模型整体已验证并优于基线。 | 仅实现/one-step范围 | Paper1 main |
| C02 | SUPPORTED | zero correction对D0为288/288 bitwise等价。 | 训练后仍保证所有轨迹bitwise等价。 | 只对冻结zero-correction测试 | Paper1 main |
| C03 | SUPPORTED | K1/K2 pair antisymmetry硬保证线动量守恒。 | 所有物理守恒与耗散均已验证。 | 角动量/耗散边界另列 | Paper1 main |
| C04 | SUPPORTED | TE1 cutoff birth/death拓扑分量通过6/6 replay和12/12 fixed-side gradients。 | neighbor search整体可微。 | piecewise fixed-side component | Paper1 main |
| C05 | CONDITIONAL | 360 probes中216具有stable epsilon windows。 | 多步梯度已资格化。 | 144失败、history 0/6 | Paper1 main negative |
| C06 | SUPPORTED | static pair-force fitting v0.2未资格。 | 静态pair correction不可学习的一般定律。 | 仅冻结dataset/protocol/arms | Paper1 negative |
| C07 | SUPPORTED | 多步AD/FD整体未资格。 | 梯度完全错误或完全不可用。 | reverse/JVP与topology分量通过 | Paper1 negative |
| C08 | NOT_TESTED | dynamic training未授权且未执行。 | 已训练动态Transformer。 | training_runs=0 | Future Paper2 |
| C09 | NOT_TESTED | autonomous rollout未执行。 | rollout稳定或优于SPH。 | rollouts=0 | Future Paper2 |
| C10 | UNSUPPORTED | Stage01最终仍为V2_QUALIFICATION_FAIL。 | Stage01 V2已恢复。 | acoustic局部PASS不覆盖shear FAIL | Prohibited |
| C11 | UNSUPPORTED | K2结构资格化但attention superiority未建立。 | Transformer优于MLP。 | 无合格公平性能比较 | Prohibited |
| C12 | NOT_TESTED | full solver improvement/cost/utility未执行。 | 求解器更准确、更快或更便宜。 | 无性能/成本证据 | Future Paper2 |
