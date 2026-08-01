# Stage 01D-R 最终报告

## 1. Stage 01D 冻结与旧 V2_FAIL 保留

正式运行提交为 `3290b65837805ae5aa15f98580ffcd7e002161ba`，最终证据提交及
annotated tag target 为 `6c910a1a6d34befa205cb12c0a1f0d0c47c1f7f4`；tag 为
`stage-01d-v2-fail-resource-gate`。SHA-256 清单包含
`15` 项、mismatch=0。

Stage 01D 的既有状态仍为 **`V2_FAIL`**，本阶段没有回写任何旧报告、配置、
轨迹、日志或失败栈。

## 2. 原资源门为何触发

旧 N32 smoke 在 step `4` 观察到 current RSS 从
233,783,296 B (233.783 MB) 增至
324,386,816 B (324.387 MB)，旧预登记规则据此给出
`MEMORY_GROWTH: sustained current RSS growth`。状态全部有限、无 sustained
system-memory pressure；因此它是有效的旧资源门失败，不是数值发散证明。

## 3. 为什么五个采样点不足以证明泄漏

五点都位于新的 25-step allocator/warm-up 区，且 current RSS 在 diagnostics
之前采样，下一点会包含上一轮 diagnostics、邻域/force 临时分配与 allocator
缓存。没有 post-warm-up quartile、稳健斜率、重复性和同步 tensor/Python-memory
证据，不能在 allocator plateau 与真实 retention 之间作唯一判定。

## 4. 静态代码保留审计

| # | YES/NO | 判断 |
|---|---|---|
| 1 | NO（accepted RK2 step 为 YES） | 保护边界不完整；正式 float 输入未证明 graph 泄漏 |
| 2 | NO | 未发现该保留源 |
| 3 | YES（通用 observer）；正式 worker 为 NO | 潜在 O(sample)；当前正式路径未触发 |
| 4 | NO（完整 state）；短任务每步保存四个主要场 | checkpoint 数有界，但 NumPy payload 会累计 |
| 5 | NO（midpoint state）；midpoint evaluation 为 YES | 单步有界引用 |
| 6 | YES（运行时有界；无轨迹 archive） | 三套 evaluation 可提高平台与瞬时峰值 |
| 7 | YES | 未发现诊断记录持有 tensor |
| 8 | NO | 未发现该保留源 |
| 9 | YES（selected checkpoints）；长轨迹不是所有 solver steps | 有界 NumPy 历史与 archive 阶段副本 |
| 10 | NO | solver 与报告内存隔离 |
| 11 | YES（一个 step 的有界引用） | 确认的 O(E) 保留，不是 O(step·E) 历史 |
| 12 | YES（异常恢复期 traceback）；generator/partial 为 NO | 仅晚期异常路径暂时持有 frame，不解释正常逐步增长 |

没有发现正式路径按 step 保存 torch-tensor 历史；确认的主要有界项是三套
force evaluation 的一个-step 生命周期与 selected NumPy checkpoint 缓冲。

## 5. A/B/C/D 四变体

| variant | name | no_grad | diagnostics | checkpoints | NPZ | steps | formal |
|---|---|---|---|---|---|---|---|
| A | solver_minimal | True | False | False | False | 500 | True |
| B | diagnostics_enabled | True | True | False | False | 500 | True |
| C | diagnostics_and_archive | True | True | True | True | 500 | True |
| D | graph_retention_sentinel | mode comparison | sentinel-only | False | False | 20 | False |

A/B/C 各三次独立 qualifying process；D 为 20-step graph sentinel，不进入
正式资源 gate。

## 6. N16/N32 对照

| variant | N16 RSS | N32 RSS | N16 RSS/particle | N32 RSS/particle | N32/N16 | N16 slope | N32 slope |
|---|---|---|---|---|---|---|---|
| A | 282,271,744 B (282.272 MB) | 346,857,472 B (346.857 MB) | 1,102,624 B (1.103 MB) | 338,728 B (0.339 MB) | 1.2288 | 1,521.371 B/step | 19,396.542 B/step |
| B | 288,235,520 B (288.236 MB) | 372,572,160 B (372.572 MB) | 1,125,920 B (1.126 MB) | 363,840 B (0.364 MB) | 1.2926 | 7,553.589 B/step | 31,734.957 B/step |
| C | 289,783,808 B (289.784 MB) | 377,176,064 B (377.176 MB) | 1,131,968 B (1.132 MB) | 368,336 B (0.368 MB) | 1.3016 | 8,570.092 B/step | 41,686.552 B/step |

## 7. Warm-up 与 post-warm-up 分离

step 0–25 仅定义 allocator/warm-up；step 26–500 才用于资源资格。first quartile
为 step 26–144，final quartile 为 382–500；所有 RSS slope、quartile 与 rolling
判定均遵循该冻结区间。

## 8. RSS、tracemalloc 与 tensor inventory

| N | variant | complete | median final-Q RSS | RSS slope | RSS positive repeats | tensor-count positive | tensor-byte positive | tracemalloc positive | GC positive |
|---|---|---|---|---|---|---|---|---|---|
| 16 | A | 3/3 | 282,271,744 B (282.272 MB) | 1,521.371 B/step | 3 | 0 | 3 | 0 | 0 |
| 16 | B | 3/3 | 288,235,520 B (288.236 MB) | 7,553.589 B/step | 3 | 0 | 3 | 0 | 0 |
| 16 | C | 3/3 | 289,783,808 B (289.784 MB) | 8,570.092 B/step | 3 | 0 | 3 | 0 | 0 |
| 32 | A | 3/3 | 346,857,472 B (346.857 MB) | 19,396.542 B/step | 3 | 0 | 3 | 0 | 0 |
| 32 | B | 3/3 | 372,572,160 B (372.572 MB) | 31,734.957 B/step | 3 | 0 | 3 | 0 | 0 |
| 32 | C | 3/3 | 377,176,064 B (377.176 MB) | 41,686.552 B/step | 3 | 0 | 3 | 0 | 0 |

## 9. Archive 与 solver 内存分离

| N | repeat | writes | checkpoints | archive RSS delta | solver quartile | solver slope | archive |
|---|---|---|---|---|---|---|---|
| 16 | 1 | 1 | 10 | 32,768 B (0.033 MB) | PASS | PASS | `06_experiments/stage_01dr_memory_diagnosis/snapshots/stage01dr_n16_vc_r1.npz` |
| 16 | 2 | 1 | 10 | 32,768 B (0.033 MB) | PASS | PASS | `06_experiments/stage_01dr_memory_diagnosis/snapshots/stage01dr_n16_vc_r2.npz` |
| 16 | 3 | 1 | 10 | 32,768 B (0.033 MB) | PASS | PASS | `06_experiments/stage_01dr_memory_diagnosis/snapshots/stage01dr_n16_vc_r3.npz` |
| 32 | 1 | 1 | 10 | 32,768 B (0.033 MB) | PASS | PASS | `06_experiments/stage_01dr_memory_diagnosis/snapshots/stage01dr_n32_vc_r1.npz` |
| 32 | 2 | 1 | 10 | 32,768 B (0.033 MB) | PASS | PASS | `06_experiments/stage_01dr_memory_diagnosis/snapshots/stage01dr_n32_vc_r2.npz` |
| 32 | 3 | 1 | 10 | 32,768 B (0.033 MB) | PASS | PASS | `06_experiments/stage_01dr_memory_diagnosis/snapshots/stage01dr_n32_vc_r3.npz` |

Archive delta 只取 `after_archive-before_archive`；它不回灌 solver post-warm-up
slope。A/B 没有 NPZ，C 仅在预登记 checkpoint 形成结束后 archive。

## 10. 任何修复的 before/after

本次分析记录 `retention_fix_applied=false`。未修改密度、EOS、压力、黏性、H/dx、dt、nu、c_s、RK2、布局或守恒结构，也没有可报告的before/after 修复曲线。静态审计发现的有界引用仅进入诊断假设，没有被事后改写成已修复缺陷。预登记理由：Static audit found bounded temporaries but no demonstrated step-growing project-side retention chain before the formal Stage 01D-R campaign.

## 11. 数值回归

REG gate 为 **PASS**；observed=
`{"bitwise_equal_count":40,"identity_pass":true,"row_count":40,"tolerance_pass_count":40}`，threshold=`{"bitwise":40,"rows":40,"tolerance":40}`。
该结果检查 finite state、守恒/拓扑诊断及冻结 step 0–4 状态；资源分析没有修改
密度、EOS、压力、黏性、H/dx、dt、nu、c_s、RK2 或布局。

## 12. 唯一资源状态

唯一资源状态为 **`RESOURCE_FAIL_LINEAR_GROWTH`**。

至少一个 N32 qualifying variant 在重复中确认 post-warm-up RSS、live tensor 或 Python memory 持续增长。

报告器只读取 status text、analysis summary 和 STATUS gate，不在报告层重新选择状态。

## 13. 是否允许建立新的 Stage 01D2 V2 协议

决策为 **`PROHIBITED`**。资源重新资格未通过，当前不得建立或启动新的 Stage 01D2 V2 协议。 即使可以准备新协议，也没有在本阶段
启动时间/空间/扰动/Mach 收敛。

## 14. 旧 Stage 01D 状态

旧 Stage 01D **仍为 `V2_FAIL`**。Stage 01D-R 的任何资源通过、条件状态或失败
均不具追溯改写效力；旧 N32 failure stack 与三份 NPZ 继续由冻结清单保护。

## 15. Stage 02 与 V3

**Stage 02 仍未开始，V3 仍未开始。** 本阶段没有训练神经网络、实现 attention、
生成学习标签或定义教师/学生求解器。

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
