# Stage 02D — State Alignment Audit

机器证据见 `../04_target_attribution/audits/state_alignment_audit.json`。

## 1. Reference identity

本审计只读取 Stage 02C 的 `stage02c_r2_dense_all_pairs_dop853_v1`。Sample acceleration comparison 定义为
同一物化 RK2 state 上的 sparse SPH RHS 与 dense all-pairs R2 RHS；DOP853 trajectory 只用于 temporal
sensitivity，不替换 sample state。

## 2. Audit results

| gate | result | evidence basis |
|---|---:|---|
| same state | 6/6 PASS | sample `state_hash` 重算、R2 record 的 `rk2_state_hash`、`same_state_evaluation=true` |
| same configuration | 6/6 PASS | configuration hash、EOS pressure 重算、kernel/support/h/mass/neighbor convention |
| same timestamp | 6/6 PASS | sample comparison time 与 R2 record/output times 一致 |
| same graph contract | 4/6 PASS | 4个正控制 edge multiset/topology 完全一致；2个 duplicate-edge 控制预期 FAIL |
| overall alignment | 4 PASS / 2 FAIL | graph hard failure 正确传播 |

由此，4个 topology-qualified records 满足

\[
S_{SPH}=S_{ref}
\]

的同状态评价合同。2个预注册 negative controls 虽同 state/config/time，但 graph 中额外一个重复有向边，不能
声称 same graph identity，必须保持 rejected。

## 3. No trajectory subtraction

没有使用 DOP853 state 与 RK2 state 的直接 trajectory subtraction 构造 `delta_a`。DOP853 state difference
只进入 temporal uncertainty ledger，且不改变 sample `state_hash`。

## 4. Boundary

同状态和同配置 PASS 只证明比较对象对齐，不证明差值是空间离散误差，也不允许 R2 自动升级为训练标签。
