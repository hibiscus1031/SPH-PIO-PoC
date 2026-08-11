# Stage 02A — Stage 01 继承边界

**事实来源：** `../00_planning/Stage01_knowledge_transfer.md`  
**规则：** 本文只迁移已冻结事实和审计资产，不修改 `stage_01_verification/` 中的任何结果。

## 1. 必须保留的 Stage 01 结论

1. Stage 01G 的唯一 V2 资格结论保持为 `V2_QUALIFICATION_FAIL`。
2. Stage 01G 的 independent acoustic gate 通过、shear gate 失败；局部通过不覆盖最终 V2 失败。
3. Stage 01H 将 shear failure 诊断为 **finite-resolution dominant**。
4. Stage 01H **未确认 viscosity operator form failure**；该未确认项不得被 Stage 02 写成已证实失败，也不得
   被用来要求追溯修改黏性算子。
5. Stage 01E 的模型形式教训保持有效：不可压 continuous exact field 与冻结 weakly-compressible/EOS
   contract 可能不对齐，不能把所有 continuum–SPH 差异称为离散误差。
6. Stage 01 的历史 PASS、FAIL、原始 smoke 失败、受控重资格与 provenance 均不可被 Stage 02 重写。

## 2. 可以迁移的资产

| 可迁移资产 | Stage 02A 的合法用途 | 不随迁移附带的结论 |
|---|---|---|
| validated/frozen SPH RHS 与 pair interaction 约定 | 定义 \(a_{\mathrm{SPH}}\) 和零修正 baseline | 不证明 PIO 有效 |
| conservation audit | 构造 pair antisymmetry、total-force 与 torque/power 合同 | 不自动保证 learned correction 守恒 |
| topology audit | 复用 minimum-image、reciprocity、duplicate/omission/exterior-edge 规则 | 不证明动态图处处可微或 edge identity 恒定 |
| MMS framework | 构造 R1 verification 与 model-form alignment 检查 | 不自动生成合格训练标签 |
| qualified semidiscrete reference 思路 | R2 隔离时间误差和状态漂移 | 不自动提供空间修正真值 |
| reference hierarchy | 区分 R1/R2/R3/RX 的用途和资格 | 不允许混合 reference class |
| independent shear/acoustic 框架 | 未来独立验证与 failure propagation | 不得默认吸收为训练数据 |
| resource/provenance/determinism 检查 | 未来标签和评价的资格字段 | 不将基础设施成功等同科学通过 |

## 3. 不能迁移的结论

- 不能迁移或声称 `V2 PASS`；
- 不能声称 learned correction effectiveness、精度提升或 rollout 改善；
- 不能由 acoustic PASS 推断 PIO generalization；
- 不能由有限分辨率诊断推断误差必然局部、可学习或可跨分辨率泛化；
- 不能由固定邻域 AD PASS 推断动态图拓扑可微；
- 不能把 Stage 01F5B 的 plateau-aware requalification 扩大为任意 reference/data 资格；
- 不能修改 benchmark、阈值或历史失败来支持未来模型。

## 4. Stage 02A 写入边界

本阶段只在 `stage_02_Particle_Interaction_Operator/` 中新增理论、约束和报告文件。禁止写入
`stage_01_verification/`。任何未来发现与 Stage 01 历史冲突时，应在 Stage 02 新报告中记录冲突，不能回写
历史产物。

## 5. 本阶段不产生的证据

本阶段没有模型实现、训练、数据集/标签生成、参数调节或 benchmark 执行，因此不产生性能、泛化、V2 升级
或 Stage 03 结论。
