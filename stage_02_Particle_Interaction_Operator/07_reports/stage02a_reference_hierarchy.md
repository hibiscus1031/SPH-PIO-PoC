# Stage 02A — Reference Hierarchy 报告

规范合同见 `../02_operator_design/reference_hierarchy/reference_hierarchy_contract.md`。

## 冻结结论

| 类别 | 来源 | 本阶段冻结用途 | 标签资格 |
|---|---|---|---|
| R1 continuum-compatible | analytic solution / MMS | verification；检查空间离散候选目标 | 仅在 WCSPH model-form alignment、同状态比较及非目标误差隔离后成为候选 |
| R2 semidiscrete-qualified | qualified high-order temporal reference | 隔离时间误差、状态漂移和空间平台 | 默认是误差分解证据，不自动是空间修正标签 |
| R3 independent benchmark | shear/acoustic 或另行冻结的独立 reference | validation | 默认禁止训练，保持独立性 |
| RX model-form-misaligned | continuous model 与冻结 SPH contract 不一致 | diagnostic only | 硬禁止训练 |

Reference class 描述生成机制和模型关系，而非简单质量排序。解析解不一定优于半离散 reference；若解析模型
与 WCSPH/EOS 不对齐，它必须进入 RX。数值精细度或较小 uncertainty 不能修复 model-form mismatch。

## 资格决策顺序

1. 先核对 continuous/semidiscrete model identity 与 forcing/EOS；
2. 再核对 baseline/reference 是否在同一状态、时刻和 configuration 上评价；
3. 再用 R2 或其他合格证据隔离时间与状态漂移；
4. 量化 reference uncertainty；
5. 应用 topology/resource/determinism 门；
6. 最后判断该差值是否是可归因 discretization component。

任一步 unresolved 时，候选保持 diagnostic/unresolved，不以有利误差结果覆盖资格缺口。

## 与 Stage 01 的关系

Stage 01E 提供 model-form alignment 的反例边界；Stage 01F 提供 MMS 与 semidiscrete 分解框架；Stage 01G
提供独立 benchmark 隔离要求。Stage 01G 的 `V2_QUALIFICATION_FAIL` 和 Stage 01H 的 finite-resolution
dominant 诊断均保持不变。
