# Stage 02B — Dataset and Target Qualification Report

**冻结日期：** 2026-08-04  
**范围：** 只设计数据协议；没有数据、trajectory、reference、训练、模型或 benchmark 执行。

## 1. Qualification scope

Stage 02B 将 Stage 02A 的数学目标转化为未来可机器审计的数据合同。它定义“一个候选 frame 必须包含什么”、
“reference 如何映射到 target”、“何时只能 diagnostic/rejected”以及“family 如何隔离”，但不创建任何实例。

## 2. Target contract

目标符号冻结为

\[
\Delta a=a_{ref}-a_{SPH},
\]

字符串为 `a_ref_minus_a_sph`。二者必须在相同 state/configuration/graph contract 下评价，且差值只在
`discretization_attributed` 后可能获得训练资格。完整合同见 `stage02b_reference_to_target_contract.md`。

## 3. Reference hierarchy

R1 continuum-compatible 是条件性训练候选；R2 semidiscrete-qualified 用于 time/state isolation；R3
independent benchmark 只用于 validation；RX model-form-misaligned 被拒绝。Class 角色不可依据结果回溯修改。

## 4. Dataset schema

`pio_dataset_schema.json` 强制 particle state、neighbor information、`a_SPH`、`a_ref`、`delta_a`、metadata、
uncertainty、provenance 和 eligibility。SHA-256 格式、reference 枚举和 sign convention 在结构层冻结；跨数组
长度、代数差值、hash 重算和 verdict 重算由未来语义验证门承担。详见 `stage02b_schema_contract.md`。

## 5. Label eligibility

YAML 规则把结论限定为 `eligible_for_future_training`、`diagnostic`、`rejected`。只有 R1 且 uncertainty、hash、
topology、resource、determinism、model-form、finite/state/attribution/leakage 全部合格时才可能 eligible。R2/R3
保持 diagnostic 角色，RX 和硬失败 rejected。详见 `stage02b_label_eligibility_report.md`。

## 6. Split strategy

禁止 random frame split。切分以 leakage-graph component 为原子单元，显式覆盖 trajectory、initial condition、
resolution、\(H/dx\)、disorder、repeat 和 benchmark family。R3 保留完整类别或预冻结严格未见参数范围。详见
`stage02b_split_strategy.md`。

## 7. Uncertainty contract

Reference/time/space/model-form/topology/resource 分账，保持 `GCI not justified` 并禁止 single total GCI。
Topology/resource failure 不作为误差条合并；model-form mismatch 不随机化。详见
`stage02b_uncertainty_contract.md`。

## 8. Provenance

`state_hash`、`configuration_hash`、`neighbor_graph_hash` 使用 SHA-256 和版本化 canonical bytes。Source、环境、
resource/determinism policy、family lineage、失败与 split policy 必须只增留存。详见
`../03_dataset/provenance/provenance_hash_contract.md`。

## 9. Stage 01 inheritance

Stage 01G `V2_QUALIFICATION_FAIL` 保持；shear failure 继续记为 finite-resolution dominant；viscosity operator
form failure 继续为 NOT CONFIRMED。没有修改 Stage 01，也不从其局部 PASS 推断标签或模型有效。

## 10. Execution boundary

本阶段只新增 Markdown、JSON Schema 和 YAML rules。没有运行 SPH/MMS/shear/acoustic，没有生成 frame、array、
manifest、trajectory、reference、target 或 split assignment，也没有实现模型、训练或性能评价。
