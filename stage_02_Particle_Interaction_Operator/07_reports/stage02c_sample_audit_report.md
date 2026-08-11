# Stage 02C — Sample Audit Report

机器审计见 `../03_dataset/audits/sample_audit.json`、`schema_validation.json` 和 `eligibility_audit.json`。

## 1. Inventory

- cases：3；
- R2 reference records：3；
- samples：6；
- positive pipeline frames：4；
- predefined rejection-control frames：2；
- reference classes：仅 `R2_semidiscrete_qualified`。

## 2. Schema and semantic audit

6/6 samples 通过 frozen JSON Schema recursive-keyword validation，且6/6通过跨字段语义检查：

- particle/edge/acceleration arrays 的长度和维度一致；
- `delta_a == a_ref - a_SPH` 在冻结 float64 容差内；
- state/config/neighbor graph identity 一致；
- 所有 sample 均为 R2；
- 没有 `split_assignment`；
- verdict/reason codes 与 eligibility engine 重新计算一致。

审计器覆盖本 schema 实际使用的 `$ref`、`oneOf`、type、required、additionalProperties、enum、const、array、
range 和 pattern 规则，并追加科学语义门；它不把结构校验称为训练资格。

## 3. Eligibility results

| verdict | count | reason |
|---|---:|---|
| `eligible_for_future_training` | 0 | R2 不允许作为本合同的主空间训练标签 |
| `diagnostic` | 4 | `DIAG_R2_TEMPORAL_REFERENCE` + `DIAG_ATTRIBUTION_UNRESOLVED` |
| `rejected` | 2 | 预注册 duplicate-edge 控制：`REJECT_TOPOLOGY` + `REJECT_FAILURE_FLAG` |

Verdict 全部由规则自动产生，`manual_override_permitted=false`。

## 4. Target integrity observations

两类正控制的 sparse/dense `delta_a` Linf 为0；负控制因一个重复有向边，Linf 约为0.09163–0.09210 m/s²，
并按预期拒绝。这些数值仅验证符号、拓扑 failure propagation 与存储，不是模型或 SPH performance 评价。

## 5. Overall audit

R2-only、schema、semantic、eligibility、provenance、pipeline hash、determinism 和 prohibited-output audit 均为
PASS。失败控制本身是预期测试输入，不使生成审计失败；它不能进入训练。
