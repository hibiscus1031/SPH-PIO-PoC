# 结构化中文摘要

## 背景

动态神经–SPH耦合同时引入时间积分、动态图重建、历史状态提交和多步自动微分；如果这些层级未被分开资格认定，结构正确性、梯度有效性与模型性能容易被混为同一结论。[REF-TODO: verification of physics-informed machine learning；SPH verification and validation]

## 方法

本文采用verification-first路线，建立D0基线、D1瞬时MLP、D2循环模型和D3因果时间注意力模型的统一动态接口，并依次审计动态参考、独立RK2、zero correction、反对称reciprocal pair-force、多步AD/FD和确定性拓扑事件。全部结论受冻结claim boundary约束。

## 结果

独立RK2的48/48检查、zero correction的288/288 bitwise等价、结构smoke的72/72、checkpoint/resume的6/6与one-step autograd的6/6均通过；冻结多阶段测试中540/540守恒检查通过。完整360-probe多步AD/FD矩阵只有216个probe获得稳定窗口，144个失败，history门为0/6；因此Stage 03D保持`DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`。确定性TE1记录一次edge birth和一次death，6/6 replay与12/12 event-side gradients通过，但edge membership仍是离散事件。

## 结论

结果支持对动态实现、零修正退化、结构守恒和TE1事件两侧语义作分层资格认定，却不支持完整多步梯度、可训练性或性能主张。Stage 03D-R将144个失败限定为mixed or unresolved。本文未执行动态训练、自主rollout或性能验证；贡献在于公开验证链及其失败边界，而非证明Transformer改进SPH。
