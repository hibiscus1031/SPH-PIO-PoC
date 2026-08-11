# Stage 02A — Open Questions 与 Stage 02B 准入要求

## 1. 未解决的理论问题

1. 在相同对称性约束下，Level 1 node residual 与 Level 2 pair-force residual 的表达能力差距有多大？
2. 若 reference target 本身含非零总力残差，守恒 pair projection 会造成何种不可约误差？该残差应判为
   reference failure、模型形式差异还是边界/外力项？
3. 只使用中心 pair force 是否足以表示目标黏性修正；若引入非中心分量，角动量与耗散之间如何取舍？
4. cutoff crossing 造成的集合不连续应以 Lipschitz bound、event-stratified test 还是显式边缘平滑约束评价？
5. R1 中 WCSPH-compatible MMS 的 forcing discretization 如何与空间离散残差严格分离？
6. R2 trajectory reference 如何提供状态对齐证据，而不把时间误差反演成伪空间标签？
7. reference uncertainty 相对接近零目标时，应采用何种绝对 floor 与分量/向量范数？
8. 周期域非中心力的角动量诊断应采用何种 unwrapped convention，才能跨 cutoff 与边界稳定比较？
9. 是否需要将 pressure-like 与 viscosity-like correction 分通道，以便分别施加功率/torque 合同？
10. 如何预先定义 correction magnitude limiter，而不把物理偏差或 reference error 隐藏为稳定化？
11. 不同 reference class 是否需要显式条件变量；若需要，如何避免模型学习 source identity 而非离散误差？
12. 独立 shear/acoustic benchmark 应保留整类还是严格未见参数范围，才能防止 validation contamination？

这些问题保持开放；Stage 02A 不通过选择网络、阈值或数据来回答它们。

## 2. Future Stage 02B 必须冻结的要求

Stage 02B 在任何执行授权前至少必须完成：

- 选定并证明允许的 reference-to-target 路径，逐类别写清 R1/R2/R3/RX 的用途；
- 冻结 WCSPH model-form alignment checklist 与 forcing/state alignment 证据；
- 冻结 reference uncertainty 估计方法、norm、绝对 floor 和资格阈值；
- 冻结 canonical serialization 与 state/config/neighbor-graph hash 版本；
- 冻结 topology/resource/determinism 门、停止线、重复次数和 failure propagation；
- 冻结完整 trajectory / initialization family / resolution family 的防泄漏切分；
- 冻结 unseen resolution、unseen disorder 与 independent benchmark 的保留矩阵；
- 冻结评价范数、短 rollout 时域、守恒/功率/torque/metamorphic tests 与 pass/fail 决策表；
- 给出 dataset generation 的独立授权门；完成协议本身不等于允许生成数据；
- 继续保持 Stage 01 只读及 `V2_QUALIFICATION_FAIL`。

## 3. Stage 02B 仍不得默认获得的授权

理论资格完成不自动授权模型实现、训练、参数调节、benchmark 修改、性能声明或 Stage 03。任何后续执行都必须
由新的明确阶段请求触发。
