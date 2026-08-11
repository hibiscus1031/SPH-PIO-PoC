# Stage 01 → Stage 02 Knowledge Transfer

**用途：**把 Stage 01 已证实的数值、资源与验证经验转换为 Stage 02 的设计约束。本文不修改任何历史状态，也不把诊断完成等同于 V2 通过。

## 1. 必须继承的事实

1. Stage 00 证明 Apple Silicon 上 CPU/MPS 的基础 PyTorch 操作可用，但完整 diffSPH 求解仍曾处于未验证状态；保守规模和 CPU reference 路线应继续保留。
2. Stage 01C 的结构保持 pair operator、拓扑审计和固定邻域原生自动微分通过，说明 PIO 可以建立在一个可审计 SPH 基线上；但固定邻域 AD 不代表拓扑可微。
3. Stage 01D/01D2 的正式 V2 失败必须保留。资源和动态无序门曾失败，后续诊断只解释机制，不能追溯改写失败。
4. Stage 01E 说明不可压 TGV exact field 与冻结 weakly-compressible/EOS 路线存在模型形式对齐问题。不能把所有 continuum–SPH 差异都命名为 discretization error。
5. Stage 01F 系列证明：MMS 连续闭合、source 注入、半离散参考、时间/空间误差和平台效应必须分开；严格总误差单调门可能被空间平台附近的误差抵消触发。
6. Stage 01F5B 的 plateau-aware 重资格通过，但原始 N64 smoke 基础设施 raw FAIL 被保留；受控重试不得用于掩盖科学失败。
7. Stage 01G 的独立 acoustic 门通过、shear 门失败，最终仍是 `V2_QUALIFICATION_FAIL`。独立验证必须与 MMS/训练数据隔离。
8. Stage 01H 将 shear 失败诊断为有限分辨率主导，未确认黏性算子形式失败；该诊断不允许重新考虑 V2 状态，也不要求修改黏性算子。

## 2. 对 PIO 定义的直接约束

- PIO 只能是增量修正：\(\mathbf a_{corr}=\mathbf a_{SPH}+\widehat{\Delta\mathbf a}\)。必须保留 \(\widehat{\Delta\mathbf a}=0\) 的基线回退。
- 标签必须在相同粒子状态、质量、EOS、支撑和邻域合同下比较 \(\mathbf a_{ref}\) 与 \(\mathbf a_{SPH}\)。
- 参考必须显式分类为 continuum、semidiscrete 或 independent benchmark reference；不同层级不能混成一个未经标注的标签集合。
- 时间积分误差、空间离散误差、forcing discretization、reference uncertainty 和模型形式偏差必须有独立字段。
- 合法 reciprocal cutoff crossing 不能被误判为拓扑缺陷；duplicate、nonreciprocal、strict-support omission 和 unexpected exterior edge 仍是硬失败。
- 线动量守恒应作为硬设计目标；黏性角动量不能在没有新证据时被扩大声称。

## 3. 对数据集设计的直接约束

- 以完整 trajectory / initialization family / resolution family 为分割单位，禁止随机拆分相邻时间帧。
- 规则、5% jitter、10% jitter、不同 \(H/dx\) 与分辨率要显式分层；不能用粒子索引作为可学习特征。
- 每条样本需记录 baseline/reference source identity、配置 hash、状态 hash、邻域统计、资源状态、参考敏感性与所有 failure flags。
- 参考不确定性不足、模型形式不一致、资源失败、非有限状态或结构拓扑缺陷样本不得进入合格训练标签；但其失败元数据应保留用于审计。
- GCI 未被证明时必须写 `GCI not justified`，不能生成虚假的单一总 GCI。

## 4. 对模型与验证的直接约束

- 未来模型须满足粒子置换不变/等变、周期 minimum-image 几何和坐标旋转等变设计；至少要有相应测试。
- 训练损失的下降不构成科学资格。必须比较未校正与校正后的加速度、短期 rollout、守恒、资源、确定性和独立 benchmark。
- Shear 和 acoustic 的独立验证角色不能被训练数据吸收；至少保留整类或严格新参数范围作为 held-out。
- 模型失败不得通过修改 Stage 01 benchmark、门槛或 V2 结果解释为通过。

## 5. 可迁移资产与不可迁移结论

### 可迁移资产

- 冻结 SPH RHS 和结构保持 pair interaction 约定；
- minimum-image 与 reciprocal topology 审计方法；
- MMS-A/MMS-B 解析闭合和 source 合同；
- qualified semidiscrete reference 思路；
- plateau-aware 时间/空间误差分解；
- 独立 shear/acoustic 设计、资源子进程策略、provenance 和确定性检查框架。

### 不可直接迁移为 Stage 02 结论

- Stage 01F5B PASS 不证明任何学习模型有效；
- Stage 01G acoustic PASS 不证明 PIO 泛化；
- Stage 01H 的有限分辨率诊断不等于已经存在可学习、可泛化的修正；
- Stage 01C 固定邻域 AD PASS 不证明动态图拓扑可微；
- 任何历史失败都不能因 Stage 02 初始化而改写。

## 6. Stage 02 启动前检查表

- [x] 研究目标冻结为 discretization error correction，而不是 SPH replacement。
- [x] \(\Delta\mathbf a=\mathbf a_{ref}-\mathbf a_{SPH}\) 符号冻结。
- [x] Stage 01 PASS / FAIL / INCOMPLETE 边界已转移。
- [x] 独立 benchmark 与训练数据隔离原则已写入。
- [x] 当前不执行训练、数据生成、模型实现、调参或 benchmark 修改。
- [ ] PIO 理论资格（未来，未执行）。
- [ ] 数据协议资格（未来，未执行）。
- [ ] 数据生成授权（未来，未申请）。
- [ ] 模型实现与训练授权（未来，未申请）。

## 7. 当前结论

Stage 01 为 Stage 02 提供了“什么可学”和“什么不能混入标签”的边界，但没有提供任何训练授权或模型性能证据。唯一合法的当前动作是完成设计与审计文档。
