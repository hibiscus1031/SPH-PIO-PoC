# PIO 未来模型评价合同

## 1. 原则

训练 loss 不是科学资格。未来任何 PIO 模型只有在 baseline、correction 与 reference 分离报告，且通过以下
八类证据后，才可讨论有效性。本合同不执行模型、rollout 或 benchmark。

## 2. 必报评价维度

1. **Acceleration correction error**：报告 \(\widehat{\Delta a}\) 对合格 \(\Delta a\) 的质量加权与分位误差，
   并同时报告 \(a_{\mathrm{SPH}}\) 与 \(a_{\mathrm{corr}}\) 对 reference 的绝对/相对误差；不得只报 residual loss。
2. **Short rollout**：在冻结积分器、步长与初态下比较 baseline/corrected/reference 的短时状态误差、稳定性和
   failure flags；不能从短 rollout 外推长期稳定。
3. **Momentum conservation**：报告 total correction force、pair antisymmetry residual、拓扑状态；Level 1 与
   Level 2 分开评价。
4. **Energy/viscous diagnostics**：报告 PIO power、压力/黏性分项、耗散符号和局部 pair torque；不把线动量
   守恒等同于能量资格。
5. **Determinism**：冻结软件/硬件、种子、归约与容差，重复运行并保留全部状态；资源失败单独记账。
6. **Unseen resolution**：按完整 resolution family 留出，禁止相邻帧或同族泄漏；与训练分辨率外推范围分开。
7. **Unseen disorder**：规则、5% jitter、10% jitter 等按 initialization/layout family 留出并分层报告。
8. **Independent benchmark**：保留 shear/acoustic 或另行冻结的独立 benchmark，不默认作为训练标签，报告
   baseline、corrected 与 reference；不得修改 Stage 01 门槛或历史状态。

## 3. 共同前置门

所有评价样本必须携带 label schema 中的 provenance/hash/status 字段；动态图允许 reciprocal cutoff crossing，
但 topology defects 为硬失败。reference uncertainty、resource status 和 determinism status 必须与误差结果同页
呈现，不能只在附录中省略。

## 4. Stage 02B 必须预先冻结的内容

未来 Stage 02B 至少要在任何数据生成前冻结：评价范数与归一化、绝对/相对 floor、容差、短 rollout 时域、
完整 holdout 单位、独立 benchmark 隔离清单、失败传播规则、重复次数、资源停止线、哈希序列化版本及
pass/fail 决策表。未冻结这些内容不得进入执行阶段。
