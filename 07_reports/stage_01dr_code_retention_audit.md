# Stage 01D-R 代码保留审计

## 1. 审计边界

本报告静态读取冻结 Stage 01D 的 `01_solver/dynamic_solver/` 与
`06_experiments/stage_01d_fixed_physics_tgv/`。报告器不导入求解 worker，
不运行 trajectory，也不把静态可疑点直接解释为内存泄漏。

Stage 01D 的既有状态仍为 **`V2_FAIL`**。Stage 01D-R 只重新评价资源行为，不回写旧状态；V3 与 Stage 02 均未开始。

## 2. 十二项直接回答

| # | 问题 | YES/NO | retention 判断 | 文件与行号 |
|---|---|---|---|---|
| 1 | 普通前向 TGV 是否完整位于 torch.no_grad() | NO（accepted RK2 step 为 YES） | 保护边界不完整；正式 float 输入未证明 graph 泄漏 | `06_experiments/stage_01d_fixed_physics_tgv/run_dynamic_verification.py:799`；`06_experiments/stage_01d_fixed_physics_tgv/run_dynamic_verification.py:1104`；`01_solver/dynamic_solver/state.py:34` |
| 2 | 是否存在 retain_graph=True | NO | 未发现该保留源 | 两个审计目录 AST/文本扫描为 0；AD 调用未设置 retain_graph。 |
| 3 | 是否向列表、字典、闭包或全局变量保存 tensor | YES（通用 observer）；正式 worker 为 NO | 潜在 O(sample)；当前正式路径未触发 | `01_solver/dynamic_solver/periodic_rollout.py:153`；`01_solver/dynamic_solver/periodic_rollout.py:157` |
| 4 | trajectory recorder 是否保存每步完整状态 | NO（完整 state）；短任务每步保存四个主要场 | checkpoint 数有界，但 NumPy payload 会累计 | `06_experiments/stage_01d_fixed_physics_tgv/run_dynamic_verification.py:817`；`06_experiments/stage_01d_fixed_physics_tgv/run_dynamic_verification.py:965` |
| 5 | 是否保存中点状态 | NO（midpoint state）；midpoint evaluation 为 YES | 单步有界引用 | `01_solver/dynamic_solver/periodic_rollout.py:94`；`01_solver/dynamic_solver/periodic_rollout.py:28` |
| 6 | 是否保存 edge index、pair displacement 或 pair force | YES（运行时有界；无轨迹 archive） | 三套 evaluation 可提高平台与瞬时峰值 | `01_solver/dynamic_solver/acceleration.py:38`；`01_solver/dynamic_solver/periodic_rollout.py:28` |
| 7 | diagnostics 是否在写 CSV 前 detach 并转成 Python 标量 | YES | 未发现诊断记录持有 tensor | `01_solver/dynamic_solver/diagnostics.py:261`；`01_solver/dynamic_solver/diagnostics.py:846`；`01_solver/dynamic_solver/diagnostics.py:1380` |
| 8 | 是否注册未移除的 forward/backward hooks | NO | 未发现该保留源 | 审计目录 hook 注册调用扫描为 0。 |
| 9 | NPZ 是否在运行中积累所有状态 | YES（selected checkpoints）；长轨迹不是所有 solver steps | 有界 NumPy 历史与 archive 阶段副本 | `06_experiments/stage_01d_fixed_physics_tgv/run_dynamic_verification.py:817`；`06_experiments/stage_01d_fixed_physics_tgv/run_dynamic_verification.py:965` |
| 10 | report generator 是否在 solver 子进程内执行 | NO | solver 与报告内存隔离 | `06_experiments/stage_01d_fixed_physics_tgv/generate_stage01d_reports.py:3` |
| 11 | accepted step 后旧 state、中点和 force result 是否仍被引用 | YES（一个 step 的有界引用） | 确认的 O(E) 保留，不是 O(step·E) 历史 | `06_experiments/stage_01d_fixed_physics_tgv/run_dynamic_verification.py:1103`；`06_experiments/stage_01d_fixed_physics_tgv/run_dynamic_verification.py:1105`；runner 无 del result |
| 12 | 是否有 generator、partial 或 traceback 保留大型局部变量 | YES（异常恢复期 traceback）；generator/partial 为 NO | 仅晚期异常路径暂时持有 frame，不解释正常逐步增长 | `06_experiments/stage_01d_fixed_physics_tgv/run_dynamic_verification.py:1233`；审计目录 Yield/partial 扫描为 0 |

## 3. 生命周期判断

静态代码中没有确认的 `O(step)` torch-tensor 历史。正式 worker 的主要确认项是
`DynamicStepResult` 在下一次赋值前同时持有 start/midpoint/end 三套
`ForceEvaluation`，以及 selected checkpoint 的 detached NumPy 缓冲。
前者是一个 step 的 `O(E)` 有界引用，后者是 `O(checkpoint·N)`，均需要动态
inventory 判断平台与峰值，但不能仅凭源码宣称线性泄漏。

通用 `rollout_periodic` observer 可以原样保存 tensor 字典；冻结的正式 Stage 01D
worker 没有使用该 API。普通 accepted RK2 step 位于 `torch.no_grad()`，但完整
forward worker 没有统一的外层 guard；当前正式配置由普通 float 构造，因此这仍是
防回归边界，而不是对旧 N32 的已证实因果归因。

## 4. 最小复现建议

| # | 静态结论 | 最小复现/回归建议 |
|---|---|---|
| 1 | NO（accepted RK2 step 为 YES） | 用 requires-grad 哨兵记录 prepare、step、diagnostics 的 grad-enabled 状态。 |
| 2 | NO | AST 回归拒绝 backward/autograd 调用中的 retain_graph=True。 |
| 3 | YES（通用 observer）；正式 worker 为 NO | observer 每步返回 positions tensor，比较 live tensor count 与纯标量 observer。 |
| 4 | NO（完整 state）；短任务每步保存四个主要场 | 比较 archive off、buffer only、stack、compression 四阶段内存。 |
| 5 | NO（midpoint state）；midpoint evaluation 为 YES | 对 midpoint state/evaluation 建立 weakref，检查 del result 前后释放。 |
| 6 | YES（运行时有界；无轨迹 archive） | 跟踪 row/displacement/force weakref 与 unique-storage bytes。 |
| 7 | YES | 用 grad-bearing 输入生成 record，断言值域仅含 JSON 标量并写临时 CSV。 |
| 8 | NO | AST 回归禁止 hook 注册，或要求 RemovableHandle 在 probe 后清零。 |
| 9 | YES（selected checkpoints）；长轨迹不是所有 solver steps | 记录每个 array.nbytes，并隔离 np.stack 与压缩阶段 RSS。 |
| 10 | NO | spy worker argv，并断言 rollout 前后报告路径保持不存在/mtime 不变。 |
| 11 | YES（一个 step 的有界引用） | 提取 next state/end 后比较 del result, previous_position 前后的 weakref。 |
| 12 | YES（异常恢复期 traceback）；generator/partial 为 NO | 晚期注入 archive 异常，run_one 返回及 gc.collect 后检查 tensor weakref。 |

## 5. 已存在的测试入口

| test source | scope | 报告边界 |
|---|---|---|
| `tests/test_stage01dr_forward_no_grad.py` | forward_no_grad | source present; execution status is not inferred by this report generator |
| `tests/test_stage01dr_diagnostics_detached.py` | diagnostics_detached | source present; execution status is not inferred by this report generator |
| `tests/test_stage01dr_no_state_history_growth.py` | no_state_history_growth | source present; execution status is not inferred by this report generator |
| `tests/test_stage01dr_neighbor_release.py` | neighbor_release | source present; execution status is not inferred by this report generator |
| `tests/test_stage01dr_archive_isolation.py` | archive_isolation | source present; execution status is not inferred by this report generator |

这些路径的存在不等同于测试已经通过；正式通过判断只能来自独立测试命令或
campaign/analysis 的机器证据。本报告不伪造 pytest 结果。

## 6. 静态结论

静态审计支持优先检查：完整 forward no-grad、三套 force evaluation 的 weakref
释放、diagnostics 临时分配、archive 四阶段及晚期异常 traceback。它不支持根据
五个旧 RSS 点宣称 Python 泄漏，也不支持忽略这些有界保留对平台与瞬时峰值的影响。

机器分析给出的唯一资源状态为 **`RESOURCE_FAIL_LINEAR_GROWTH`**；静态报告不重新
推导或覆盖该状态。

## 证据索引

| path | SHA-256 | bytes |
|---|---|---|
| `01_solver/dynamic_solver/acceleration.py` | `9835e5a67b177d1991ba8fab80109dc1ab5ea1d783a403b1c8b391d3b809771e` | 6575 |
| `01_solver/dynamic_solver/diagnostics.py` | `f1f39d9fb1edc547fb051aa34524894ec3239a4c375c15c6f1ac42367f7ae5a7` | 51316 |
| `01_solver/dynamic_solver/periodic_rollout.py` | `95453a1726185c5cc8f65d67ae867a366e4e0dfc10dddcc3570b9fa7c9abe1e4` | 5412 |
| `01_solver/dynamic_solver/state.py` | `8df0c49aee8271fe9c107f4776e4ce4e3c8f35e68584261c0efa34cc9eda0561` | 3866 |
| `06_experiments/stage_01d_fixed_physics_tgv/generate_stage01d_reports.py` | `e1c284f1a09096d47c409b1e2c191962e0688ac63c717d7e71f31e77ac366f3d` | 90421 |
| `06_experiments/stage_01d_fixed_physics_tgv/logs/smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0_failure.txt` | `dd94eceeeeb4e380c4aaebb262f38ae4aae6d6e83a77d00b3be3dd85ee77ad5e` | 241 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/run_summary.csv` | `74f96bd7d9bbb3cecb164221a6ac8d1c8eb9502b06aefe670bb530f41df47a06` | 6532 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt` | `7bd1685c7a729a27af2b89caf66a1a5fbaecaa951ae47f26406b58636df0dc1e` | 8 |
| `06_experiments/stage_01d_fixed_physics_tgv/results/trajectory_samples/smoke_n32_increasing_neighbor_n32_h5p00_dt0p00050000_tf0p010_cs20p0_regular_s0.csv` | `3a14895da85a32dc70bfd1a6c1738b484a3cea20038d2a5ac1bc4fa86f9cbb61` | 12036 |
| `06_experiments/stage_01d_fixed_physics_tgv/run_dynamic_verification.py` | `3d0dc75113fdb5dd1cf8cfb7efb6e3104c63055d6229dc3da34ecb0b1b750e27` | 71279 |
| `06_experiments/stage_01dr_memory_diagnosis/configs/preregistered_memory_diagnosis.yml` | `1d0fbdaeba85d26a6c76b2d04079393b3dff704c0ede9de35726859870bf6dc8` | 11804 |
| `06_experiments/stage_01dr_memory_diagnosis/generate_stage01dr_reports.py` | `0a751334bc0672dcbacba4fc9f1156741bd66f3d42fc82df1ed952977fdb6756` | 101841 |
| `06_experiments/stage_01dr_memory_diagnosis/results/analysis_summary.json` | `077c0b83d0b2ca4a6fde5112412503ce49f09c6b752a5006b316ca8f36fbc412` | 1115 |
| `06_experiments/stage_01dr_memory_diagnosis/results/archive_assessment.csv` | `e514fea7934d0c62f17c329ea8e1c07ad4eedddd457471388c7158055145d374` | 1942 |
| `06_experiments/stage_01dr_memory_diagnosis/results/resource_gate_evidence.csv` | `f64b52fb06ad83a0ad753094843eb1238898f9701c0cb3eaa0a03e1b64ead92b` | 5306 |
| `06_experiments/stage_01dr_memory_diagnosis/results/stage01d_frozen_sha256_manifest.csv` | `049fb50ad20f228036ba57b9022828b86e016da4be11e19e0aebfa1db9641a23` | 2394 |
| `06_experiments/stage_01dr_memory_diagnosis/results/stage01dr_resource_status.txt` | `11935afa1196493662fb86c9c037d21cf7ba7e883370aa274ef56d02f8109e8f` | 28 |
| `tests/test_stage01dr_archive_isolation.py` | `49e52241bb80a01fa08e206d1209676bd04a14814707d2a8c34b1fa035a546ac` | 3462 |
| `tests/test_stage01dr_diagnostics_detached.py` | `46cddc7fdd5eb4c1bb7e00d1b2f29d8711cfedc1217be0b6a84e8bdcc9949e8a` | 4081 |
| `tests/test_stage01dr_forward_no_grad.py` | `d806ef14ca69dced71a0b85c4e733b3c15757b1d7d24a4519198f92fb6da2056` | 3607 |
| `tests/test_stage01dr_neighbor_release.py` | `4acef5624e31c1bebe710cb5bd9a9ae10984144258151879a9190df8001f74a6` | 1714 |
| `tests/test_stage01dr_no_state_history_growth.py` | `a4031bf5dda4630088ddaef66dc0075ba7ec5e4821f1c67d19901288a40c369b` | 1704 |

## 最终边界

Stage 01D 的既有状态仍为 **`V2_FAIL`**。Stage 01D-R 只重新评价资源行为，不回写旧状态；V3 与 Stage 02 均未开始。
