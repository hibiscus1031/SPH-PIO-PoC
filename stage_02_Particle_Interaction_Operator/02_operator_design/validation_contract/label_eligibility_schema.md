# PIO Label Eligibility Schema

**性质：** 未来标签元数据的冻结 schema；本文件不生成数据或标签。

## 1. 最小记录

每个候选 \(\Delta a\) 必须具备以下字段。缺少任一必填字段时，资格结论只能是 `ineligible`。

| 字段 | 类型/枚举 | 资格含义 |
|---|---|---|
| `reference_class` | `R1_continuum_compatible` / `R2_semidiscrete_qualified` / `R3_independent_benchmark` / `RX_model_form_misaligned` | reference hierarchy 身份 |
| `reference_uncertainty` | 结构体：`value`, `norm`, `units`, `method`, `evidence_uri` | 与目标同单位、同范数的不确定性及来源；不得只写 unknown 数值 |
| `state_hash` | 非空内容哈希 | 同一物理时刻完整 canonical state 的身份 |
| `configuration_hash` | 非空内容哈希 | RHS、EOS、kernel、support、precision、forcing、integrator 配置身份 |
| `neighbor_graph_hash` | 非空内容哈希 | canonical directed/undirected edge set、minimum-image convention 与支撑身份 |
| `failure_flags` | 非空数组（可为空集合 `[]`） | 所有 scientific/infrastructure failure；不得丢弃失败记录 |
| `topology_status` | `pass` / `fail` / `unresolved`，并含 defect counts | reciprocal、duplicate、omission、exterior-edge 状态 |
| `resource_status` | `pass` / `fail` / `unresolved`，并含设备、峰值资源与停止线身份 | 资源失败不得伪装为科学结果 |
| `determinism_status` | `pass` / `fail` / `unresolved`，并含重复次数、容差与种子/环境身份 | 单次成功不等于确定性合格 |
| `model_form_compatibility` | `compatible` / `misaligned` / `unresolved`，并含证据 | RX 或 unresolved 不能训练 |

为使标签本身可审计，还必须包含：

| 字段 | 类型/枚举 | 说明 |
|---|---|---|
| `schema_version` | 固定字符串 | 防止不同资格规则静默混用 |
| `sample_id` | 唯一字符串 | 记录身份，不得作为可学习粒子特征 |
| `baseline_source_id` / `reference_source_id` | provenance 字符串 | 代码、制品与版本身份 |
| `comparison_time` | 数值及单位 | 明确同状态/同时刻比较 |
| `target_definition` | 固定为 `a_ref_minus_a_sph` | 防止符号翻转 |
| `target_component_attribution` | `discretization_attributed` / `mixed` / `unresolved` | 只有第一项可继续资格化 |
| `error_component_status` | 对 space/time/reference/forcing/model-form/cross 的状态映射 | 误差分解证据 |
| `reference_independence` | `independent` / `not_independent` / `not_applicable` / `unresolved` | R3 及 inverse-crime 审计 |
| `eligibility_verdict` | `eligible_for_future_training` / `diagnostic_only` / `ineligible` | 由规则导出，不由人工偏好覆盖 |
| `evidence_uris` | 非空列表 | 指向 reference、topology、resource、determinism 报告 |

## 2. Canonical hash 合同

- `state_hash` 必须覆盖粒子物理量、质量、粒子身份的 canonical ordering、数值 dtype/字节序与时刻；
- `configuration_hash` 必须覆盖所有影响 baseline/reference 的配置，不能只 hash 文件名；
- `neighbor_graph_hash` 必须覆盖排序后的边、周期像/MI convention、support rule 与 reciprocal 表示；
- hash 算法及序列化版本必须写入 schema/version provenance；
- 浮点近似相等不能由相同 hash 表示；如需容差分组，另设 group id，不能覆盖内容身份。

## 3. 资格判定逻辑

`eligible_for_future_training` 仅在以下条件同时成立时可导出：

1. `reference_class` 为经相应用途批准的 R1；R2 仅在未来另有明确目标证明时可候选；R3 默认保留验证；RX 硬禁止；
2. reference uncertainty 已量化且通过 Stage 02B 预先冻结的相对/绝对门；
3. state/config/graph 三个 hash 完整，baseline/reference 状态对齐；
4. `failure_flags=[]`；
5. topology、resource、determinism 全部为 `pass`；
6. model form 为 `compatible`；
7. target attribution 为 `discretization_attributed`，非目标误差项均已隔离、受界或不适用；
8. 不存在 reference leakage、benchmark contamination 或 inverse crime。

任一条件失败必须保留记录并给出 machine-readable reason code；不得删除失败样本后宣称数据全部合格。

## 4. 明确非授权

该 schema 的冻结不授权物化标签、运行求解器、创建数据集、划分训练集或选择数值阈值。它只规定未来若产生
候选记录，必须如何证明其资格。
