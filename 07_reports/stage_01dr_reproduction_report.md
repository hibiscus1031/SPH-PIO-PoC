# Stage 01D-R 复现报告

## 1. 原 Stage 01D 触发事件

冻结 run `smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0` 在 step `4`、物理时间
`0.002` 触发 **`MEMORY_GROWTH`**，保留原因是
`sustained current RSS growth`。current RSS 从 233,783,296 B (233.783 MB) 增至
324,386,816 B (324.387 MB)，区间差为 90,603,520 B (90.604 MB)。
该运行的 `all_states_finite=True`、
`sustained_memory_pressure=False`；因此旧证据证明的是
预登记资源门被触发，不证明数值发散，也不证明泄漏机制。

| step | time | current RSS | peak RSS | edges | finite |
|---|---|---|---|---|---|
| 0 | 0.0 | 233,783,296 B (233.783 MB) | 267,796,480 B (267.796 MB) | 82944 | True |
| 1 | 0.0005 | 301,056,000 B (301.056 MB) | 301,056,000 B (301.056 MB) | 76640 | True |
| 2 | 0.001 | 312,246,272 B (312.246 MB) | 312,262,656 B (312.263 MB) | 76640 | True |
| 3 | 0.0015 | 315,785,216 B (315.785 MB) | 315,785,216 B (315.785 MB) | 76640 | True |
| 4 | 0.002 | 324,386,816 B (324.387 MB) | 324,386,816 B (324.387 MB) | 76640 | True |

## 2. 为什么五个点不足以证明泄漏

旧 runner 在每个 sample 的 diagnostics **之前**采 current RSS，随后执行完整
topology audit、pair-force 重算和 RK2。step 0→1 因而混合首轮 diagnostics、
首次算子分配、CPU allocator/cache 以及一个 step 的 bounded result lifetime。
五个点全部位于新的 25-step warm-up 边界内，没有 post-warm-up quartile、稳健
斜率、重复性或 live tensor 同步证据，不能区分 allocator 平台与真实 retention。

## 3. 固定复现配置

N32 保持 particles=1024、H/dx=5.0、dt=5e-4、c_s=20、nu=0.02、regular、
seed=0、float64、CPU；N16 使用冻结 smoke 离散作为规模对照。A/B/C 各三个
独立子进程、500 步，D 比较 20 步 no-grad 与 grad-enabled。

## 4. A/B/C 重复结果

| N | variant | complete | numeric | reclaimed | median final-Q RSS | median RSS slope | RSS positive repeats | tensor-count positive | tensor-byte positive | tracemalloc positive | GC positive |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 16 | A | 3/3 | PASS | PASS | 282,271,744 B (282.272 MB) | 1,521.371 B/step | 3 | 0 | 3 | 0 | 0 |
| 16 | B | 3/3 | PASS | PASS | 288,235,520 B (288.236 MB) | 7,553.589 B/step | 3 | 0 | 3 | 0 | 0 |
| 16 | C | 3/3 | PASS | PASS | 289,783,808 B (289.784 MB) | 8,570.092 B/step | 3 | 0 | 3 | 0 | 0 |
| 32 | A | 3/3 | PASS | PASS | 346,857,472 B (346.857 MB) | 19,396.542 B/step | 3 | 0 | 3 | 0 | 0 |
| 32 | B | 3/3 | PASS | PASS | 372,572,160 B (372.572 MB) | 31,734.957 B/step | 3 | 0 | 3 | 0 | 0 |
| 32 | C | 3/3 | PASS | PASS | 377,176,064 B (377.176 MB) | 41,686.552 B/step | 3 | 0 | 3 | 0 | 0 |

## 5. N16/N32 规模对照

| variant | N16 median RSS | N32 median RSS | N16 RSS/particle | N32 RSS/particle | N32/N16 | N16 slope | N32 slope |
|---|---|---|---|---|---|---|---|
| A | 282,271,744 B (282.272 MB) | 346,857,472 B (346.857 MB) | 1,102,624 B (1.103 MB) | 338,728 B (0.339 MB) | 1.2288 | 1,521.371 B/step | 19,396.542 B/step |
| B | 288,235,520 B (288.236 MB) | 372,572,160 B (372.572 MB) | 1,125,920 B (1.126 MB) | 363,840 B (0.364 MB) | 1.2926 | 7,553.589 B/step | 31,734.957 B/step |
| C | 289,783,808 B (289.784 MB) | 377,176,064 B (377.176 MB) | 1,131,968 B (1.132 MB) | 368,336 B (0.368 MB) | 1.3016 | 8,570.092 B/step | 41,686.552 B/step |

## 6. Graph-retention sentinel

| mode | status | graph nodes | position gradFn | velocity gradFn | RSS | live tensors | tensor storage | reclaimed |
|---|---|---|---|---|---|---|---|---|
| no_grad | PASS | 0 | False | False | 301,334,528 B (301.335 MB) | 20 | 3,841,344 B (3.841 MB) | PASS |
| grad_enabled | PASS | 4677 | True | True | 1,044,283,392 B (1044.283 MB) | 3174 | 1,360,056,240 B (1360.056 MB) | PASS |

SENTINEL gate：**PASS**；它只展示 autograd graph
对照，不纳入 A–J 的正式资源通过判定。

## 7. 冻结数值状态回归

REG gate：**PASS**。observed：
`{"bitwise_equal_count":40,"identity_pass":true,"row_count":40,"tolerance_pass_count":40}`；threshold：`{"bitwise":40,"rows":40,"tolerance":40}`。
该 gate 比较 N16/N32 的 step 0–4 positions、velocities、densities、pressures，
不把内存结论替代为数值结论。

## 8. 复现结论

唯一资源状态为 **`RESOURCE_FAIL_LINEAR_GROWTH`**。至少一个 N32 qualifying variant 在重复中确认 post-warm-up RSS、live tensor 或 Python memory 持续增长。
原 Stage 01D 的五点失败证据原样保留，没有被删除或重命名。

## 证据索引

| path | SHA-256 | bytes |
|---|---|---|
| `06_experiments/stage_01d_fixed_physics_tgv/logs/smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0_failure.txt` | `dd94eceeeeb4e380c4aaebb262f38ae4aae6d6e83a77d00b3be3dd85ee77ad5e` | 241 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/run_summary.csv` | `74f96bd7d9bbb3cecb164221a6ac8d1c8eb9502b06aefe670bb530f41df47a06` | 6532 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt` | `7bd1685c7a729a27af2b89caf66a1a5fbaecaa951ae47f26406b58636df0dc1e` | 8 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0.csv` | `3a14895da85a32dc70bfd1a6c1738b484a3cea20038d2a5ac1bc4fa86f9cbb61` | 12036 |
| `06_experiments/stage_01dr_memory_diagnosis/configs/preregistered_memory_diagnosis.yml` | `1d0fbdaeba85d26a6c76b2d04079393b3dff704c0ede9de35726859870bf6dc8` | 11804 |
| `06_experiments/stage_01dr_memory_diagnosis/generate_stage01dr_reports.py` | `0a751334bc0672dcbacba4fc9f1156741bd66f3d42fc82df1ed952977fdb6756` | 101841 |
| `06_experiments/stage_01dr_memory_diagnosis/results/analysis_summary.json` | `077c0b83d0b2ca4a6fde5112412503ce49f09c6b752a5006b316ca8f36fbc412` | 1115 |
| `06_experiments/stage_01dr_memory_diagnosis/results/archive_assessment.csv` | `e514fea7934d0c62f17c329ea8e1c07ad4eedddd457471388c7158055145d374` | 1942 |
| `06_experiments/stage_01dr_memory_diagnosis/results/graph_sentinel_summary.csv` | `964d312076a0d38a4f01f702377b45d7856c98a585499519fec0a2af4755fea8` | 566 |
| `06_experiments/stage_01dr_memory_diagnosis/results/memory_run_metrics.csv` | `acf019fe57e86346271241526bb4fcaf39dfa74677f2be7f6e7022714c3c3360` | 28038 |
| `06_experiments/stage_01dr_memory_diagnosis/results/resource_gate_evidence.csv` | `f64b52fb06ad83a0ad753094843eb1238898f9701c0cb3eaa0a03e1b64ead92b` | 5306 |
| `06_experiments/stage_01dr_memory_diagnosis/results/stage01d_frozen_sha256_manifest.csv` | `049fb50ad20f228036ba57b9022828b86e016da4be11e19e0aebfa1db9641a23` | 2394 |
| `06_experiments/stage_01dr_memory_diagnosis/results/stage01dr_resource_status.txt` | `11935afa1196493662fb86c9c037d21cf7ba7e883370aa274ef56d02f8109e8f` | 28 |
| `06_experiments/stage_01dr_memory_diagnosis/results/variant_summary.csv` | `0ee8ec5b5e3d1a43ff9c8baa27469615460cf796e9e04f06c972f34e3cc00d97` | 1604 |

## 最终边界

Stage 01D 的既有状态仍为 **`V2_FAIL`**。Stage 01D-R 只重新评价资源行为，不回写旧状态；V3 与 Stage 02 均未开始。
