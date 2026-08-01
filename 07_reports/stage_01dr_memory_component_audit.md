# Stage 01D-R 内存组件审计

## 1. 预登记测量结构

每个 rollout 位于独立串行子进程。current RSS 与 peak RSS 是不同字段；
tensor inventory 只在稀疏检查点运行。前 25 步是 allocator/warm-up 区，
step 26–500 才进入
资源判定。

| phase | 用途 |
|---|---|
| process_start | 在 heavy imports 前建立进程基线 |
| imports_complete | 隔离 import/运行时装载成本 |
| initial_state_complete | 隔离初始状态分配 |
| first_neighborhood_complete | 隔离首个邻域与算子分配 |
| warmup_complete | 结束 step 0–25 allocator/warm-up 区 |
| solver_step | 对 step 26–500 进行 post-warm-up 评价 |
| before_archive | 记录 archive 前 current RSS |
| after_archive | 定位 NPZ archive 增量 |
| before_process_exit | 记录退出前状态并验证父进程回收 |

solver RSS cadence 为每 5 步一次；archive checkpoint
固定为 `[0, 1, 2, 3, 4, 25, 100, 250, 400, 500]`，不得按结果调整。

## 2. A/B/C/D 隔离变体

| variant | name | no_grad | diagnostics | state checkpoints | final NPZ | steps | formal gate |
|---|---|---|---|---|---|---|---|
| A | solver_minimal | True | False | False | False | 500 | True |
| B | diagnostics_enabled | True | True | False | False | 500 | True |
| C | diagnostics_and_archive | True | True | True | True | 500 | True |
| D | graph_retention_sentinel | mode comparison | sentinel-only | False | False | 20 | False |

Variant D 仅作为 graph-retention sentinel，不进入正式资源资格判定。

## 3. 18 个 qualifying run

| N | variant | repeat | complete | numeric | first-Q RSS | final-Q RSS | final-first | Theil–Sen | bootstrap 95% CI | tensor-count slope | tensor-byte slope | tracemalloc slope | GC-object slope | mean step | final edges |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 16 | A | 1 | PASS | PASS | 279,265,280 B (279.265 MB) | 285,900,800 B (285.901 MB) | 6,635,520 B (6.636 MB) | 6,917.689 B/step | [4,610.492 B/step, 8,128.503 B/step] | 0/step | 38.400 B/step | 80.872 B/step | 0/step | 0.040122 s | 12928 |
| 16 | A | 2 | PASS | PASS | 281,722,880 B (281.723 MB) | 282,271,744 B (282.272 MB) | 548,864 B (0.549 MB) | 1,061.444 B/step | [624.313 B/step, 1,321.792 B/step] | 0/step | 38.400 B/step | 64.608 B/step | 0/step | 0.040075 s | 12928 |
| 16 | A | 3 | PASS | PASS | 279,396,352 B (279.396 MB) | 279,838,720 B (279.839 MB) | 442,368 B (0.442 MB) | 1,521.371 B/step | [1,015.986 B/step, 1,937.472 B/step] | 0/step | 38.400 B/step | 109.400 B/step | 0/step | 0.039774 s | 12928 |
| 16 | B | 1 | PASS | PASS | 287,768,576 B (287.769 MB) | 288,235,520 B (288.236 MB) | 466,944 B (0.467 MB) | 1,438.595 B/step | [1,171.136 B/step, 1,651.161 B/step] | 0/step | 38.400 B/step | 323.702 B/step | 0/step | 0.040545 s | 12928 |
| 16 | B | 2 | PASS | PASS | 282,681,344 B (282.681 MB) | 286,490,624 B (286.491 MB) | 3,809,280 B (3.809 MB) | 7,553.589 B/step | [3,676.342 B/step, 10,044.429 B/step] | 0/step | 38.400 B/step | 319.839 B/step | 0/step | 0.040569 s | 12928 |
| 16 | B | 3 | PASS | PASS | 285,687,808 B (285.688 MB) | 290,947,072 B (290.947 MB) | 5,259,264 B (5.259 MB) | 9,485.474 B/step | [5,609.690 B/step, 12,022.927 B/step] | 0/step | 38.400 B/step | 320.113 B/step | 0/step | 0.040520 s | 12928 |
| 16 | C | 1 | PASS | PASS | 288,145,408 B (288.145 MB) | 292,880,384 B (292.880 MB) | 4,734,976 B (4.735 MB) | 15,961.187 B/step | [12,485.105 B/step, 18,583.052 B/step] | 0/step | 38.400 B/step | 399.287 B/step | 0/step | 0.040369 s | 12928 |
| 16 | C | 2 | PASS | PASS | 289,513,472 B (289.513 MB) | 289,783,808 B (289.784 MB) | 270,336 B (0.270 MB) | 840.205 B/step | [554.224 B/step, 1,069.944 B/step] | 0/step | 38.400 B/step | 395.156 B/step | 0/step | 0.040447 s | 12928 |
| 16 | C | 3 | PASS | PASS | 283,926,528 B (283.927 MB) | 289,374,208 B (289.374 MB) | 5,447,680 B (5.448 MB) | 8,570.092 B/step | [3,505.162 B/step, 12,179.951 B/step] | 0/step | 38.400 B/step | 401.939 B/step | 0/step | 0.040099 s | 12928 |
| 32 | A | 1 | PASS | PASS | 339,386,368 B (339.386 MB) | 346,857,472 B (346.857 MB) | 7,471,104 B (7.471 MB) | 7,016.271 B/step | [744.930 B/step, 11,092.413 B/step] | 0/step | 10.240 B/step | 78.861 B/step | 0/step | 0.115318 s | 80224 |
| 32 | A | 2 | PASS | PASS | 337,395,712 B (337.396 MB) | 344,244,224 B (344.244 MB) | 6,848,512 B (6.849 MB) | 19,396.542 B/step | [12,034.697 B/step, 25,048.316 B/step] | 0/step | 10.240 B/step | 94.590 B/step | 0/step | 0.116786 s | 80224 |
| 32 | A | 3 | PASS | PASS | 341,229,568 B (341.230 MB) | 365,363,200 B (365.363 MB) | 24,133,632 B (24.134 MB) | 61,615.543 B/step | [51,885.558 B/step, 69,139.281 B/step] | 0/step | 10.240 B/step | 84.756 B/step | 0/step | 0.118459 s | 80224 |
| 32 | B | 1 | PASS | PASS | 359,653,376 B (359.653 MB) | 375,455,744 B (375.456 MB) | 15,802,368 B (15.802 MB) | 42,173.630 B/step | [24,719.616 B/step, 54,248.439 B/step] | 0/step | 10.240 B/step | 324.444 B/step | 0/step | 0.115680 s | 80224 |
| 32 | B | 2 | PASS | PASS | 359,219,200 B (359.219 MB) | 369,737,728 B (369.738 MB) | 10,518,528 B (10.519 MB) | 12,136.296 B/step | [3,393.061 B/step, 17,293.216 B/step] | 0/step | 10.240 B/step | 319.782 B/step | 0/step | 0.116871 s | 80224 |
| 32 | B | 3 | PASS | PASS | 359,415,808 B (359.416 MB) | 372,572,160 B (372.572 MB) | 13,156,352 B (13.156 MB) | 31,734.957 B/step | [17,730.483 B/step, 41,119.623 B/step] | 0/step | 10.240 B/step | 326.318 B/step | 0/step | 0.114662 s | 80224 |
| 32 | C | 1 | PASS | PASS | 365,969,408 B (365.969 MB) | 380,387,328 B (380.387 MB) | 14,417,920 B (14.418 MB) | 41,686.552 B/step | [28,970.523 B/step, 51,312.981 B/step] | 0/step | 10.240 B/step | 674.020 B/step | 0/step | 0.116463 s | 80224 |
| 32 | C | 2 | PASS | PASS | 361,725,952 B (361.726 MB) | 377,176,064 B (377.176 MB) | 15,450,112 B (15.450 MB) | 45,616.398 B/step | [36,605.498 B/step, 51,376.619 B/step] | 0/step | 10.240 B/step | 666.297 B/step | 0/step | 0.116459 s | 80224 |
| 32 | C | 3 | PASS | PASS | 361,603,072 B (361.603 MB) | 367,050,752 B (367.051 MB) | 5,447,680 B (5.448 MB) | 17,283.514 B/step | [9,893.045 B/step, 22,018.114 B/step] | 0/step | 10.240 B/step | 672.640 B/step | 0/step | 0.115659 s | 80224 |

## 4. Variant 聚合与重复性

| N | variant | complete | numeric | sampling | reclaimed | median final-Q RSS | RSS/particle | median RSS slope | RSS positive repeats | tensor-count positive | tensor-byte positive | tracemalloc positive | GC positive |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 16 | A | 3/3 | PASS | PASS | PASS | 282,271,744 B (282.272 MB) | 1,102,624 B (1.103 MB) | 1,521.371 B/step | 3 | 0 | 3 | 0 | 0 |
| 16 | B | 3/3 | PASS | PASS | PASS | 288,235,520 B (288.236 MB) | 1,125,920 B (1.126 MB) | 7,553.589 B/step | 3 | 0 | 3 | 0 | 0 |
| 16 | C | 3/3 | PASS | PASS | PASS | 289,783,808 B (289.784 MB) | 1,131,968 B (1.132 MB) | 8,570.092 B/step | 3 | 0 | 3 | 0 | 0 |
| 32 | A | 3/3 | PASS | PASS | PASS | 346,857,472 B (346.857 MB) | 338,728 B (0.339 MB) | 19,396.542 B/step | 3 | 0 | 3 | 0 | 0 |
| 32 | B | 3/3 | PASS | PASS | PASS | 372,572,160 B (372.572 MB) | 363,840 B (0.364 MB) | 31,734.957 B/step | 3 | 0 | 3 | 0 | 0 |
| 32 | C | 3/3 | PASS | PASS | PASS | 377,176,064 B (377.176 MB) | 368,336 B (0.368 MB) | 41,686.552 B/step | 3 | 0 | 3 | 0 | 0 |

## 5. Diagnostics 组件（B 相对 A）

| N | A final-Q RSS | B final-Q RSS | bounded extra | fraction of A | gate H |
|---|---|---|---|---|---|
| 16 | 282,271,744 B (282.272 MB) | 288,235,520 B (288.236 MB) | 5,963,776 B (5.964 MB) | 2.113% | PASS |
| 32 | 346,857,472 B (346.857 MB) | 372,572,160 B (372.572 MB) | 25,714,688 B (25.715 MB) | 7.414% | PASS |

该差异仅描述有 diagnostics 与最小 solver 的有界平台差，不等同于逐步泄漏。

## 6. Archive 组件（Variant C）

| N | repeat | writes | checkpoints | after-before RSS | solver quartile | solver slope | archive |
|---|---|---|---|---|---|---|---|
| 16 | 1 | 1 | 10 | 32,768 B (0.033 MB) | PASS | PASS | `06_experiments/stage_01dr_memory_diagnosis/snapshots/stage01dr_n16_vc_r1.npz` |
| 16 | 2 | 1 | 10 | 32,768 B (0.033 MB) | PASS | PASS | `06_experiments/stage_01dr_memory_diagnosis/snapshots/stage01dr_n16_vc_r2.npz` |
| 16 | 3 | 1 | 10 | 32,768 B (0.033 MB) | PASS | PASS | `06_experiments/stage_01dr_memory_diagnosis/snapshots/stage01dr_n16_vc_r3.npz` |
| 32 | 1 | 1 | 10 | 32,768 B (0.033 MB) | PASS | PASS | `06_experiments/stage_01dr_memory_diagnosis/snapshots/stage01dr_n32_vc_r1.npz` |
| 32 | 2 | 1 | 10 | 32,768 B (0.033 MB) | PASS | PASS | `06_experiments/stage_01dr_memory_diagnosis/snapshots/stage01dr_n32_vc_r2.npz` |
| 32 | 3 | 1 | 10 | 32,768 B (0.033 MB) | PASS | PASS | `06_experiments/stage_01dr_memory_diagnosis/snapshots/stage01dr_n32_vc_r3.npz` |

Archive 写入发生在 solver step 结束后；只有 `before_archive` 到 `after_archive`
的增量可以归因于 archive。solver step 内的 post-warm-up 趋势必须由 A/B/C 的
`solver_step` 样本独立判断。

## 7. Graph sentinel

| mode | status | reachable graph nodes | position grad_fn | velocity gradFn | step-20 RSS | live tensors | tensor storage | reclaimed | identity |
|---|---|---|---|---|---|---|---|---|---|
| no_grad | PASS | 0 | False | False | 301,334,528 B (301.335 MB) | 20 | 3,841,344 B (3.841 MB) | PASS | PASS |
| grad_enabled | PASS | 4677 | True | True | 1,044,283,392 B (1044.283 MB) | 3174 | 1,360,056,240 B (1360.056 MB) | PASS | PASS |

## 8. 图件

- `06_experiments/stage_01dr_memory_diagnosis/figures/stage01dr_n16_memory_curves.png`
- `06_experiments/stage_01dr_memory_diagnosis/figures/stage01dr_n32_memory_curves.png`
- `06_experiments/stage_01dr_memory_diagnosis/figures/stage01dr_graph_sentinel.png`

图件只可视化 retained machine evidence，不改变 gate 或唯一状态。

## 9. 组件结论

唯一资源状态为 **`RESOURCE_FAIL_LINEAR_GROWTH`**。至少一个 N32 qualifying variant 在重复中确认 post-warm-up RSS、live tensor 或 Python memory 持续增长。

## 证据索引

| path | SHA-256 | bytes |
|---|---|---|
| `06_experiments/stage_01d_fixed_physics_tgv/logs/smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0_failure.txt` | `dd94eceeeeb4e380c4aaebb262f38ae4aae6d6e83a77d00b3be3dd85ee77ad5e` | 241 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/run_summary.csv` | `74f96bd7d9bbb3cecb164221a6ac8d1c8eb9502b06aefe670bb530f41df47a06` | 6532 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt` | `7bd1685c7a729a27af2b89caf66a1a5fbaecaa951ae47f26406b58636df0dc1e` | 8 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0.csv` | `3a14895da85a32dc70bfd1a6c1738b484a3cea20038d2a5ac1bc4fa86f9cbb61` | 12036 |
| `06_experiments/stage_01dr_memory_diagnosis/configs/preregistered_memory_diagnosis.yml` | `1d0fbdaeba85d26a6c76b2d04079393b3dff704c0ede9de35726859870bf6dc8` | 11804 |
| `06_experiments/stage_01dr_memory_diagnosis/figures/stage01dr_graph_sentinel.png` | `2cf4f04724d01feef51f4aa6156330c1c7dd72037cd28124513ddef4c15bcb22` | 41975 |
| `06_experiments/stage_01dr_memory_diagnosis/figures/stage01dr_n16_memory_curves.png` | `018d35735b6e71743f1ad13ff454f34fb46baf20cc4f464b0ba6fe70b3253d7e` | 88441 |
| `06_experiments/stage_01dr_memory_diagnosis/figures/stage01dr_n32_memory_curves.png` | `7844ca18ccb8b9c6caaba345a8f6a2775b9e3f0ea10a530755d31a11a06d2c34` | 97077 |
| `06_experiments/stage_01dr_memory_diagnosis/generate_stage01dr_reports.py` | `0a751334bc0672dcbacba4fc9f1156741bd66f3d42fc82df1ed952977fdb6756` | 101841 |
| `06_experiments/stage_01dr_memory_diagnosis/results/analysis_summary.json` | `077c0b83d0b2ca4a6fde5112412503ce49f09c6b752a5006b316ca8f36fbc412` | 1115 |
| `06_experiments/stage_01dr_memory_diagnosis/results/archive_assessment.csv` | `e514fea7934d0c62f17c329ea8e1c07ad4eedddd457471388c7158055145d374` | 1942 |
| `06_experiments/stage_01dr_memory_diagnosis/results/diagnostics_overhead.csv` | `16f6564d68f6cc6adf8b7bb7d9da995783fb640d4758f754c05acf2ccfad39bc` | 291 |
| `06_experiments/stage_01dr_memory_diagnosis/results/graph_sentinel_summary.csv` | `964d312076a0d38a4f01f702377b45d7856c98a585499519fec0a2af4755fea8` | 566 |
| `06_experiments/stage_01dr_memory_diagnosis/results/memory_run_metrics.csv` | `acf019fe57e86346271241526bb4fcaf39dfa74677f2be7f6e7022714c3c3360` | 28038 |
| `06_experiments/stage_01dr_memory_diagnosis/results/resource_gate_evidence.csv` | `f64b52fb06ad83a0ad753094843eb1238898f9701c0cb3eaa0a03e1b64ead92b` | 5306 |
| `06_experiments/stage_01dr_memory_diagnosis/results/stage01d_frozen_sha256_manifest.csv` | `049fb50ad20f228036ba57b9022828b86e016da4be11e19e0aebfa1db9641a23` | 2394 |
| `06_experiments/stage_01dr_memory_diagnosis/results/stage01dr_resource_status.txt` | `11935afa1196493662fb86c9c037d21cf7ba7e883370aa274ef56d02f8109e8f` | 28 |
| `06_experiments/stage_01dr_memory_diagnosis/results/variant_summary.csv` | `0ee8ec5b5e3d1a43ff9c8baa27469615460cf796e9e04f06c972f34e3cc00d97` | 1604 |

## 最终边界

Stage 01D 的既有状态仍为 **`V2_FAIL`**。Stage 01D-R 只重新评价资源行为，不回写旧状态；V3 与 Stage 02 均未开始。
