# Stage 01D-R 资源重新资格报告

## 1. 唯一状态

本阶段唯一资源状态为 **`RESOURCE_FAIL_LINEAR_GROWTH`**。

至少一个 N32 qualifying variant 在重复中确认 post-warm-up RSS、live tensor 或 Python memory 持续增长。

该状态只回答 frozen fixed-physics solver 的资源行为，不是新的 V2 solution
verification 结论。

## 2. 预登记阈值

| criterion | registered threshold |
|---|---|
| first/final quartile RSS delta | 100,000,000 B (100.000 MB) |
| first/final quartile fractional increase | 20.000% |
| Theil–Sen RSS slope | 200,000.000 B/step |
| Variant B extra RSS | 100,000,000 B (100.000 MB) and 20.000% |
| Variant C archive increment | 100,000,000 B (100.000 MB) and 20.000% |
| current RSS safety stop | 8,000,000,000 B (8000.000 MB) |
| minimum separation/dx | >= 0.25 |
| relative pair-force residual | <= 1e-12 |
| normalized internal force | <= 1e-10 |

## 3. A–J 与辅助硬门

| gate | check | pass | observed | threshold | severity | source | detail |
|---|---|---|---|---|---|---|---|
| A | n32_variant_a_required_complete | PASS | 3 | 3 | HARD | `results/run_summaries/*.json` | — |
| B | n32_variant_b_required_complete | PASS | 3 | 3 | HARD | `results/run_summaries/*.json` | — |
| C | n32_variant_c_minimum_complete | PASS | 3 | >=2 | HARD | `results/run_summaries/*.json` | — |
| D | all_numerical_topology_and_system_resource_gates | PASS | {"numerical":true,"resource":true} | {"numerical":true,"resource":true} | HARD | `results/numerical_samples/*.csv + results/memory_samples/*.jsonl` | — |
| E | postwarmup_quartile_rss_bounds | PASS | 18/18 | 18/18 | HARD | `results/memory_run_metrics.csv` | — |
| F | postwarmup_rss_slope_bounds | PASS | 18/18 | 18/18 | HARD | `results/memory_run_metrics.csv` | — |
| G | live_tensor_count_and_bytes_not_repeatedly_positive | FAIL | [{"bytes_positive":3,"count_positive":0,"resolution":16,"trusted":3,"variant":"A"},{"bytes_positive":3,"count_positive":0,"resolution":16,"trusted":3,"variant":"B"},{"bytes_positive":3,"count_positive":0,"resolution":16,"trusted":3,"variant":"C"},{"bytes_positive":3,"count_positive":0,"resolution":32,"trusted":3,"variant":"A"},{"bytes_positive":3,"count_positive":0,"resolution":32,"trusted":3,"variant":"B"},{"bytes_positive":3,"count_positive":0,"resolution":32,"trusted":3,"variant":"C"}] | required trusted repeats and fewer than 2 positive repeats | HARD | `results/variant_summary.csv` | — |
| H | variant_b_extra_memory_bounded | PASS | [{"a_median_final_quartile_rss_bytes":282271744.0,"b_median_final_quartile_rss_bytes":288235520.0,"b_minus_a_bounded_extra_bytes":5963776.0,"b_minus_a_fraction_of_a":0.02112778245349276,"evidence_complete":true,"pass":true,"resolution":16},{"a_median_final_quartile_rss_bytes":346857472.0,"b_median_final_quartile_rss_bytes":372572160.0,"b_minus_a_bounded_extra_bytes":25714688.0,"b_minus_a_fraction_of_a":0.07413618006187855,"evidence_complete":true,"pass":true,"resolution":32}] | {"bytes":100000000,"fraction":0.2} | HARD | `results/diagnostics_overhead.csv` | — |
| I | variant_c_archive_localized_and_bounded | PASS | {"bounded":true,"localized":true,"n32_archive_only_failures":0} | {"archive_only_failures":"<=1","bounded":true,"localized":true} | HARD | `results/archive_assessment.csv + snapshots/*.npz` | — |
| J | all_child_processes_reclaimed | PASS | 22/22 | 22/22 | HARD | `results/process_exit/*.json` | — |
| P | freeze_provenance_sampling_order_and_source_complete | PASS | {"campaign_order":{"expected_run_count":18,"identity_exact":true,"index_path":"06_experiments/stage_01dr_memory_diagnosis/results/campaign_qualifying_index.csv","observed_run_count":18,"order_exact":true,"serial_nonoverlap":true},"freeze":{"categories":{"failure_stack":1,"gate_evidence":1,"report":8,"run_summary":1,"state_archive":3,"status":1},"final_evidence_commit":"6c910a1a6d34befa205cb12c0a1f0d0c47c1f7f4","formal_run_commit":"3290b65837805ae5aa15f98580ffcd7e002161ba","manifest_rows":15,"mismatches":0,"old_status":"V2_FAIL","tag":"stage-01d-v2-fail-resource-gate","tag_target":"6c910a1a6d34befa205cb12c0a1f0d0c47c1f7f4"},"raw_worker_provenance":true,"retention_fix_contract":true,"schedule":true,"source_changes":[],"source_tree_clean":true} | True | HARD | `freeze manifest + run configs + campaign index + memory traces + git status` | — |
| N16 | all_n16_scale_controls_complete | PASS | 9 | 9 | HARD | `results/run_summaries/*.json` | — |
| REG | frozen_first_four_state_regression | PASS | {"bitwise_equal_count":40,"identity_pass":true,"row_count":40,"tolerance_pass_count":40} | {"bitwise":40,"rows":40,"tolerance":40} | HARD | `results/numerical_samples/stage01dr_frozen_regression_*.csv` | — |
| SENTINEL | no_grad_vs_grad_graph_sentinel | PASS | [{"evidence_error":"","final_current_rss_bytes":301334528,"final_live_tensor_count":20,"final_live_tensor_unique_storage_bytes":3841344,"final_positions_has_grad_fn":false,"final_velocities_has_grad_fn":false,"identity_pass":true,"live_tensor_bytes_delta_from_no_grad":0,"live_tensor_count_delta_from_no_grad":0,"mode":"no_grad","process_reclaimed":true,"reachable_grad_graph_node_count":0,"rss_delta_from_no_grad_bytes":0,"run_id":"stage01dr_d_no_grad_n32_r1","status":"PASS"},{"evidence_error":"","final_current_rss_bytes":1044283392,"final_live_tensor_count":3174,"final_live_tensor_unique_storage_bytes":1360056240,"final_positions_has_grad_fn":true,"final_velocities_has_grad_fn":true,"identity_pass":true,"live_tensor_bytes_delta_from_no_grad":1356214896,"live_tensor_count_delta_from_no_grad":3154,"mode":"grad_enabled","process_reclaimed":true,"reachable_grad_graph_node_count":4677,"rss_delta_from_no_grad_bytes":742948864,"run_id":"stage01dr_d_grad_enabled_n32_r1","status":"PASS"}] | no_grad graph=0; grad-enabled graph>0; both reclaimed | HARD | `results/graph_sentinel_summary.csv` | — |
| STATUS | decision_valid_and_unique | PASS | RESOURCE_FAIL_LINEAR_GROWTH | ["RESOURCE_CONDITIONAL","RESOURCE_FAIL_LINEAR_GROWTH","RESOURCE_FAIL_UNRESOLVED","RESOURCE_PASS_AFTER_RETENTION_FIX","RESOURCE_PASS_ALLOCATOR_PLATEAU"] | STATUS | `configs/preregistered_memory_diagnosis.yml` | {"ambiguous_growth": false, "confirmed_linear": true, "hard_complete": false, "isolated_overhead_only": false, "retention_fix_applied": false} |

报告层不重新计算或覆盖 `STATUS`；status text、analysis summary 与 STATUS row
已经过三方一致性校验。

## 4. 完成性与数值安全

N32 A/B 要求 3/3 完成，C 要求至少 2/3；N16 九个 scale-control run、
N16/N32 step 0–4 冻结状态回归、所有 child reclamation、拓扑、finite state、
pair-force、internal-force、viscous-power 与 minimum-separation 均由相应 gate
单独记录。资源通过不能覆盖任何数值或 provenance 失败。

## 5. Post-warm-up 资源判定

判定仅使用 step 26–500。RSS 使用 Theil–Sen、first/final quartile median、
rolling 50-step increase 与 moving-block bootstrap；tensor count/storage、
tracemalloc 与 GC tracked objects 分开报告。单次正斜率不自动构成重复性失败。

## 6. Diagnostics 与 archive

Gate H 比较 B 相对 A 的 final-quartile 平台；Gate I 要求 C 的 archive 只在
solver 后写一次、checkpoint 列表精确匹配、solver slope/quartile 有界且
archive current-RSS 增量满足注册上限。peak RSS 从未被当作 current RSS。

## 7. Retention fix

本次分析记录 `retention_fix_applied=false`。未修改密度、EOS、压力、黏性、H/dx、dt、nu、c_s、RK2、布局或守恒结构，也没有可报告的before/after 修复曲线。静态审计发现的有界引用仅进入诊断假设，没有被事后改写成已修复缺陷。预登记理由：Static audit found bounded temporaries but no demonstrated step-growing project-side retention chain before the formal Stage 01D-R campaign.

## 8. Stage 01D2 决策

决策：**`PROHIBITED`**。资源重新资格未通过，当前不得建立或启动新的 Stage 01D2 V2 协议。

即使允许“准备”协议，也必须先重新预登记并由用户另行授权；本程序没有运行
时间/空间收敛，也没有启动 V3。

## 9. 旧状态与阶段边界

Stage 01D 的既有状态仍为 **`V2_FAIL`**。Stage 01D-R 只重新评价资源行为，不回写旧状态；V3 与 Stage 02 均未开始。

Stage 01D-R 的资源状态不得替换 `stage01d_v2_status.txt`，不得据此宣称旧
N32 已完成 V2，也不得据此开始神经网络训练或生成标签。

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
| `06_experiments/stage_01dr_memory_diagnosis/results/diagnostics_overhead.csv` | `16f6564d68f6cc6adf8b7bb7d9da995783fb640d4758f754c05acf2ccfad39bc` | 291 |
| `06_experiments/stage_01dr_memory_diagnosis/results/graph_sentinel_summary.csv` | `964d312076a0d38a4f01f702377b45d7856c98a585499519fec0a2af4755fea8` | 566 |
| `06_experiments/stage_01dr_memory_diagnosis/results/memory_run_metrics.csv` | `acf019fe57e86346271241526bb4fcaf39dfa74677f2be7f6e7022714c3c3360` | 28038 |
| `06_experiments/stage_01dr_memory_diagnosis/results/resource_gate_evidence.csv` | `f64b52fb06ad83a0ad753094843eb1238898f9701c0cb3eaa0a03e1b64ead92b` | 5306 |
| `06_experiments/stage_01dr_memory_diagnosis/results/stage01d_frozen_sha256_manifest.csv` | `049fb50ad20f228036ba57b9022828b86e016da4be11e19e0aebfa1db9641a23` | 2394 |
| `06_experiments/stage_01dr_memory_diagnosis/results/stage01dr_resource_status.txt` | `11935afa1196493662fb86c9c037d21cf7ba7e883370aa274ef56d02f8109e8f` | 28 |
| `06_experiments/stage_01dr_memory_diagnosis/results/variant_summary.csv` | `0ee8ec5b5e3d1a43ff9c8baa27469615460cf796e9e04f06c972f34e3cc00d97` | 1604 |
