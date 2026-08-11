# Stage 02A — Label Eligibility 报告

规范 schema 见 `../02_operator_design/validation_contract/label_eligibility_schema.md`。

## 必填十项

任何未来 \(\Delta a\) 在进入训练资格判断前必须具有：

1. reference class；
2. reference uncertainty；
3. state hash；
4. configuration hash；
5. neighbor graph hash；
6. failure flags；
7. topology status；
8. resource status；
9. determinism status；
10. model-form compatibility。

此外必须记录 schema/version、baseline/reference provenance、比较时刻、固定差值符号
`a_ref_minus_a_sph`、误差分量状态、目标归因、reference independence、证据 URI 与机器可读资格 verdict。

## 硬门

只有 model form compatible、reference uncertainty 合格、三类 hash 完整、failure flags 为空、topology /
resource / determinism 全部通过、且差值被归因为 discretization component 时，才可标记
`eligible_for_future_training`。R3 默认保留独立验证，RX 永久为 diagnostic/ineligible；R2 默认用于误差隔离，
不自动提供空间标签。

## 失败数据政策

失败或 unresolved 的候选记录不得静默删除。它们应保留 reason code 和证据，用于审计，但不能混入合格标签。
hash 是精确内容身份；容差相似度不得覆写 hash。样本 ID 只用于审计，不得成为可学习的粒子特征。

## 当前边界

本文只冻结 schema 和判定逻辑，没有生成、物化、筛选或划分任何数据，也没有选择 uncertainty 阈值。
