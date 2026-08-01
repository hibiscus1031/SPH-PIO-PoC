# Stage 01F3-R sparse/dense 等价性

## 独立路径

Dense RHS 枚举 N16 的全部非自粒子对，使用周期最小像、严格 `r<H`、冻结的 mass/kernel/EOS/pressure/viscosity/source/state-vector 公式。它不调用 neighbor search，不创建 edge identity，也不替换生产 sparse solver。Density 仍按冻结定义包含 self kernel；非自 pair force 排除 `i=j`。互易粒子对几何按一个 canonical displacement 及其精确反向量表示，聚合不依赖输入 edge ordering。

## 覆盖范围

共比较 461 个状态：MMS-A 与 MMS-B 初态、Stage 01F3 MMS-B baseline 的 21 个保存/插值状态、3 个随机小扰动状态、216 个 cutoff 事件的前后共 432 个状态，以及 3 个 `q=1-epsilon, 1, 1+epsilon` 人工状态。比较量包括 density、pressure、pressure acceleration、viscosity acceleration、MMS source、total acceleration、`dx/dt` 与 `dv/dt`。

## 最大差异与硬门

| 量 | 最大 absolute Linf | 最大 relative Linf | 结果 |
|---|---:|---:|---|
| density | 0 | 0 | PASS (`<=1e-13`) |
| pressure | 0 | 0 | PASS (`<=1e-13`) |
| pressure acceleration | 5.385e-15 | 2.221e-15 | PASS |
| viscosity acceleration | 3.886e-16 | 1.097e-15 | PASS |
| MMS source | 0 | 0 | PASS |
| total acceleration | 5.440e-15 | 3.460e-15 | PASS (`abs<=1e-12`, `rel<=1e-11`) |
| dx/dt | 0 | 0 | PASS |
| dv/dt | 5.440e-15 | 3.460e-15 | PASS |

全部值 finite。恰好在 cutoff 时，sparse tolerance edge 可以存在而 dense 严格排除；该边的实际核与 pair contribution 为零，聚合 RHS 仍在门内。

唯一结果：**PASS**。证据：`06_experiments/stage_01f3r_reference_qualification/results/sparse_dense_equivalence.csv` 与 `sparse_dense_equivalence_summary.json`。
