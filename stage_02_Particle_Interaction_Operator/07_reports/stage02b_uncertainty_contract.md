# Stage 02B — Uncertainty Contract Report

规范合同见 `../03_dataset/uncertainty/uncertainty_contract.md`。

## 冻结账本

每个未来候选记录必须分列：

1. reference uncertainty；
2. time error；
3. space error；
4. model-form uncertainty；
5. topology uncertainty；
6. resource uncertainty。

各项携带 availability、value kind、method、qualification rule、status 与 evidence。分类不确定性不得为求和而
伪造数值；`UNRESOLVED` 不等于零。

## GCI 结论

冻结为 `GCI not justified`，且 `single_total_gci_permitted=false`。这些分量并非天然独立、同分布或均满足
渐近网格收敛条件，禁止生成 single total GCI。未来若某个明确空间子问题证明满足前置条件，也只能报告该
component-specific GCI，不覆盖其他不确定度。

## Reference uncertainty 资格

“Available”要求 value/类别、units、norm、method、rule id、status 和 evidence 完整。具体 reference campaign
必须在生成前冻结 absolute floor、相对规则、零目标处理及 coverage 解释；不得使用生成后的 target/R3 分布
调节。只有 available 且 qualification PASS 才能通过未来训练资格门。

## Failure 处理

Topology/resource failure 不是可与数值误差相加的 uncertainty bar；它们触发 rejected。Model-form mismatch
进入 RX/rejected，不能作为随机误差平均掉。Cross terms 仍由 target attribution 单独说明。
