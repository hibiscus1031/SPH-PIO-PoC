# Stage 02B Family-Level Split Strategy

**性质：** 未来切分协议；不创建 split manifest，不分配任何现有或未来样本。

## 1. 核心规则

切分必须在数据生成前按 **family level** 冻结。禁止 random frame split；禁止把同一 frame 的粒子/邻域视图、
相邻时间帧、deterministic repeats 或同一 trajectory 的派生样本分到不同 split。

## 2. 必须记录的 family axes

每个候选 frame 必须具有：

- `trajectory_family`：共同初态与推进来源下的完整 trajectory；
- `initial_condition_family`：同一解析/物理初态、参数化初态或 seed lineage；
- `resolution_family`：粒子数/空间尺度家族；
- `h_over_dx_family`：\(H/dx\) 或 support-path 家族；
- `disorder_family`：regular、5% jitter、10% jitter 及其 seed lineage；
- `deterministic_repeat_family`：同一科学配置的重复执行；
- `solution_or_benchmark_family`：MMS/analytic/source-free benchmark 的最高层身份。

这些字段是 split/provenance 元数据，不得作为粒子级可学习身份特征。

## 3. 原子切分单元

先建立 leakage graph。若两个记录满足以下任一关系，则连边：同一 frame、同一 trajectory、相同 initial-condition
lineage、deterministic repeat、同一原始 frame 派生的 neighborhood view，或由重启/重采样/格式转换形成直接
派生关系。该图的 connected component 是最低原子切分单元，必须整体分配。

随后按评价目标施加更高层 holdout：

- unseen resolution：选定的完整 `resolution_family` 不得出现在 future train；
- unseen support：选定的完整 `h_over_dx_family` 不得出现在 future train；
- unseen disorder：选定的完整 disorder level 或 seed lineage 不得出现在 future train；
- unseen initial condition：完整 initial-condition family 保留；
- independent validation：R3 完整类别或严格未见参数范围保留。

一个 frame 同时命中多个 holdout 时，按 `R3_independent_validation > future_test > future_validation >
future_train` 的优先级进入最严格隔离区，不得复制到多个区。

## 4. 允许的未来 split 身份

- `future_train`：仅接收通过标签资格且未命中任何 holdout 的 R1 候选；
- `future_validation`：用于预先定义的开发期选择，不与 test/R3 混用；
- `future_test`：完整未见 family，用于一次性内部资格评价；
- `R3_independent_validation`：独立 benchmark，只用于最终 validation；
- `unassigned`：生成前协议或资格未完成，不得训练。

Stage 02B 不实际创建这些集合。

## 5. Shear/acoustic 隔离

在数据生成前，campaign manifest 必须为每一 R3 family 选择并冻结以下之一：

1. **whole-class holdout**：完整 shear 或 acoustic 类别均不进入训练；
2. **strict-unseen-range holdout**：预先冻结参数轴、闭合训练区间和不相交验证区间，并证明无 trajectory、初态、
   resolution、\(H/dx\)、disorder 或 seed lineage 交叉。

不得查看 benchmark 结果后从 whole-class 改为有利的参数范围，也不得把 Stage 01G acoustic PASS 当作训练先验或
把 shear failure 过滤掉。

## 6. 防泄漏控制

- normalization/scaling 统计只能由 `future_train` 或预定义物理常数得到；
- reference tolerance、uncertainty 门和 eligibility 规则不得用 validation/test/R3 结果选择；
- 近重复检查必须覆盖 state/config/graph hashes 与 family lineage，而不只比较 sample ID；
- split manifest 必须只增版本、带 hash 和规则版本；结果产生后禁止就地重分配；
- 被拒绝/diagnostic 记录保留在审计清单，但不混入 train counts；
- 所有 frame 子视图继承原 frame split。

## 7. 未来 manifest 最小字段

`split_policy_version`、family axes、atomic component id、assignment、holdout reason、reference class、资格
verdict、state/config/graph hashes、parent/derived lineage、assignment timestamp、policy hash 和批准证据。manifest
只能在另行授权的数据阶段物化。
