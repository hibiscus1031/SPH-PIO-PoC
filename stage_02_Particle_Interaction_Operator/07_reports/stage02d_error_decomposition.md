# Stage 02D — Error Decomposition and Attribution Ledger

机器账本见 `../04_target_attribution/decomposition/error_decomposition_ledger.json`。

## 1. Frozen equation

\[
\Delta a
=\Delta a_{space}
+\Delta a_{time}
+\Delta a_{reference}
+\Delta a_{forcing}
+\Delta a_{model\text{-}form}
+cross.
\]

每个 sample、每一项均记录 `status`、`evidence`、`uncertainty` 和 `attribution_confidence`。本式是归因账本，
不是声称这些分量已被唯一数值相加识别。

## 2. Topology-qualified R2 records

4个正控制的 observed \(\Delta a\) 为0，但分解结论仍是 `diagnostic`：

- `space`：`UNRESOLVED_NOT_OBSERVED_BY_R2_ASSEMBLY_EQUIVALENCE`。Dense/sparse 等价只验证 assembly，未提供
  continuum-compatible spatial reference；
- `time`：报告 DOP853 sensitivity 与 RK2-vs-DOP853 acceleration difference，但无 smallness threshold，故为
  `BOUNDED_REPORTED_NO_SMALLNESS_THRESHOLD`；
- `reference`：roundoff 与 DOP853 sensitivity 有界，信心只限 audit reference；
- `forcing`：两路径均为零且匹配；
- `model-form`：仅在相同 R2 semidiscrete contract 内相容；未测试 continuum WCSPH alignment；
- `cross`：未解析。

因此不能把 `delta_a=0` 写成“空间离散误差为零”，也不能写成“operator corrected”。

## 3. Negative controls

2个 duplicate-edge samples 的 target vector L2 约0.01527–0.01535 m/s²、Linf 约0.09163–0.09211 m/s²。
该差异明确由 graph duplication 污染，`delta_a_space=REJECTED_TOPOLOGY_CONTAMINATED`，整条记录保持
rejected。其他分量不能覆盖此 hard failure。

## 4. Attribution conclusion

当前账本为4 diagnostic、2 rejected、0 discretization-attribution PASS。`all difference = discretization error`
明确为 false。
