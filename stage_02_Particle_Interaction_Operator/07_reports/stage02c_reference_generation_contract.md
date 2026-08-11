# Stage 02C — R2 Reference Generation Contract

## 1. Allowed reference

第一批只允许 `R2_semidiscrete_qualified`，identity 为
`stage02c_r2_dense_all_pairs_dop853_v1`。R3 independent benchmark 被硬禁止；R1 未通过本批次所需的独立
WCSPH model-form alignment，故不进入候选。

## 2. Same-state acceleration reference

对每个物化 RK2 state \(\mathcal S_t\)：

\[
a_{SPH}(\mathcal S_t)=\text{sparse directed-edge RHS},
\qquad
a_{ref}(\mathcal S_t)=\text{dense all-pairs RHS}.
\]

两条路径使用相同 WCSPH/EOS/kernel/support 参数，但不同 assembly path；reference 不使用另一 trajectory 的
加速度替换同状态值。目标严格为

\[
\Delta a=a_{ref}(\mathcal S_t)-a_{SPH}(\mathcal S_t).
\]

## 3. Temporal qualifier

同一 initial state 另由 DOP853 在 `rtol/atol = 1e-10/1e-12` 与 `1e-12/1e-14` 两层推进。其作用是记录 R2
temporal/state sensitivity：

- primary 与 sensitivity solver 3/3 cases 均 success；
- time error 字段记录同一时刻 RK2 state 与 DOP853 state 经 dense RHS 后的 acceleration difference；
- DOP853 state 不替换 sample `state_hash`，也不直接构造空间标签。

## 4. Reference uncertainty

`a_ref` 的审计级数值不确定度由 dense forward/reverse float64 summation 的 Linf 差异给出，并对预冻结
machine-epsilon bound 判定。6/6 records 为 available/PASS；观测范围约为
`1.11e-16`–`2.22e-16 m s^-2`。该 roundoff audit 不等于 continuum uncertainty 或空间资格。

## 5. Qualification boundary

正控制中 sparse/dense target 逐位为零，表示本批次的等价 assembly audit 通过，而非精度/性能提升。R2 在
Stage 02B 下仍是 temporal/state diagnostic，`target_component_attribution=unresolved`，因此不能获得
`eligible_for_future_training`。
