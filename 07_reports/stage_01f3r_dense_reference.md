# Stage 01F3-R dense DOP853 半离散参考

## 配置与资格门

MMS-A、MMS-B 均使用 N16、`H/dx=4.06155281280883`、`t_final=0.01` 和 41 个共同物理时刻。Dense all-pairs RHS 不使用项目 RK2、neighbor search 或 edge identity。

| 层 | rtol | atol | max_step | nfev（A/B） |
|---|---:|---:|---:|---:|
| baseline | 1e-12 | 1e-14 | 3.125e-5 | 3965 / 3965 |
| tighter | 1e-13 | 1e-15 | 1.5625e-5 | 7805 / 7805 |
| third | 1e-13 | 1e-15 | 7.8125e-6 | 15497 / 15497 |

全部参考状态 finite。代码 hash、参数 hash、配置 hash、容差、nfev 及 NPZ SHA-256 均保存在对应 qualification JSON。

## 三层敏感性

| 解 | 比较 | position Linf | velocity Linf | 门 `<=1e-9` |
|---|---|---:|---:|---|
| MMS-A | baseline/tighter | 2.554e-15 | 5.074e-14 | PASS |
| MMS-A | tighter/third | 3.997e-15 | 5.385e-14 | PASS |
| MMS-B | baseline/tighter | 2.554e-15 | 3.159e-14 | PASS |
| MMS-B | tighter/third | 4.108e-15 | 3.120e-14 | PASS |

## 原 sparse 与 dense（41 时刻）

比较 unwrapped position、velocity、density、pressure 与 total acceleration。

| 解/层 | position | velocity | density | pressure | total acceleration |
|---|---:|---:|---:|---:|---:|
| A baseline sparse/dense | 1.388e-17 | 3.331e-16 | 0 | 0 | 4.663e-15 |
| A tighter sparse/dense | 0 | 2.220e-16 | 0 | 0 | 4.441e-15 |
| B baseline sparse/dense | 1.110e-16 | 1.027e-15 | 4.441e-16 | 1.776e-13 | 4.690e-13 |
| B tighter sparse/dense | 1.110e-16 | 1.332e-15 | 4.441e-16 | 1.776e-13 | 2.587e-13 |

MMS-B sparse/dense 状态差低于 dense 自身敏感性量级；原 sparse baseline/tighter 在旧 11 个时刻与 Stage 01F3 保存轨迹的 Linf 均为 0。旧失败轨迹没有被删除或改写。结果说明 edge identity switching 是邻域表示变化，而不是半离散 RHS 的有限不连续。

证据：`06_experiments/stage_01f3r_reference_qualification/results/mms_a_reference_qualification.json`、`mms_b_reference_qualification.json` 及 `references/` 下四个 NPZ。
