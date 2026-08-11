# Stage 02B — Dataset Schema Contract Report

规范 schema 见 `../03_dataset/schema/pio_dataset_schema.json`，版本为 `pio-dataset-frame-1.0.0`。

## 顶层必填对象

Schema 强制包含：

- `particle_state`：粒子数、维度、位置、速度、密度、压力、质量和 support；
- `neighbor_information`：有向边、reciprocal pair、minimum-image 几何、graph hash 和 topology audit；
- `a_SPH`：冻结 baseline 加速度、source id 和 configuration hash；
- `a_ref`：reference 加速度、class、method、同状态与 model-form 状态；
- `delta_a`：目标值、固定符号、归因与符号复核状态；
- `metadata`：时刻、单位、三个 family/identity 维度、失败/资源/确定性状态；
- `uncertainty`：六项分账及固定 `GCI not justified`；
- `provenance`：source/environment/policy/serialization 身份；
- `eligibility`：规则版本、verdict、reason codes、state alignment 和 leakage status。

Schema 同时要求 `sample_id` 和版本身份，但 sample/particle ID 仅用于审计，禁止作为模型特征。

## 符号和 reference 枚举

`delta_a.sign_convention` 由 JSON `const` 冻结为 `a_ref_minus_a_sph`。Reference class 只接受
`R1_continuum_compatible`、`R2_semidiscrete_qualified`、`R3_independent_benchmark`、
`RX_model_form_misaligned`。

## 结构校验与语义校验边界

JSON Schema 可验证字段、类型、枚举、hash 形式和必填关系，但 Draft 2020-12 不能独立证明所有跨数组语义。
未来语义验证器还必须检查：

1. 所有粒子字段长度等于 `particle_count`，向量长度等于 `dimension`；
2. 所有 edge 字段长度一致、索引合法、reciprocal pair 完整；
3. `a_SPH`、`a_ref`、`delta_a` 长度与粒子数一致；
4. 逐分量验证 `delta_a = a_ref - a_SPH`；
5. state/config/graph hashes 与重新 canonicalized 内容一致；
6. verdict 与 YAML 规则重新计算结果一致。

通过 JSON Schema 仅表示结构合格，不等于标签 eligible。

## 本阶段边界

该 JSON 是 schema 文档，不是 dataset instance；本阶段没有创建 frame、manifest、统计或标签。
