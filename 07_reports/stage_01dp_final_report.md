# Stage 01D-P 最终报告

## 1. R5 冻结

R5 最终证据提交为 `f4262b71d1f5fb4763535a34e8187c1b1e02bcaa`；annotated tag `stage-01dr5-bounded-gc-delay-confirmed` target 为 `f4262b71d1f5fb4763535a34e8187c1b1e02bcaa`；状态 `R5_BOUNDED_GC_DELAY_CONFIRMED` 保持不变。

## 2. 2000-step R5 证据与 1600-step 最大计划轨迹

| source | t_final | minimum dt | steps | repeats | pass |
|---|---|---|---|---|---|
| Stage 01D primary/time-convergence configuration | 0.2 | 0.000125 | 1600 | n/a | True |
| Stage 01D-R5 G1 default-GC evidence | n/a | n/a | 2000 | 3 | True |

最大计划步数由 `0.2 / 0.000125 = 1600` 明确得到；R5 default-GC horizon 为 2000。

## 3. 有界 GC 延迟的运行解释

R5 表明 GC-disabled 路径线性累积，而默认 GC 的 2000-step 上包络有界。
本政策把资源安全裁决放在最大单轨迹能否在明确 RSS、时间、数值、拓扑及进程回收边界内完成，
不要求 retired count 每步为零、后半程必有全量归零，也不要求 live tensor 原始斜率严格为零。

## 4. 正式子进程政策

正式运行政策固定为：每条轨迹一个独立子进程；默认 cyclic GC 启用；
前向处于 `torch.no_grad()`；不在时间循环中调用 `gc.collect()`，也不关闭 cyclic GC；
父进程不接收 Tensor、neighborhood 或完整 state；只保留标量 diagnostics 与相对证据路径；
轨迹结束即退出子进程；AD 检查必须使用另一短程进程。

## 5. 三个 maximum-horizon canary

| run | steps | finite | GC | no_grad | topology | pair residual max | viscous power max | current RSS | peak RSS | RSS Δquartile | RSS relative | time ratio | system avail min | pass |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stage01dp_canary_r1 | 1600 | True | True | True | True | 4.57e-18 | -0.657 | 308183040 | 308183040 | 20963328 | 0.0730 | 1.0089 | 0.3827 | True |
| stage01dp_canary_r2 | 1600 | True | True | True | True | 4.57e-18 | -0.657 | 308658176 | 308658176 | 19759104 | 0.0684 | 1.0072 | 0.3801 | True |
| stage01dp_canary_r3 | 1600 | True | True | True | True | 4.57e-18 | -0.657 | 300957696 | 300957696 | 17661952 | 0.0623 | 1.0066 | 0.3761 | True |

## 6. RSS、运行时间、数值安全和拓扑

上表逐次记录 current/peak RSS、首末四分位 RSS、step-time 比率、系统可用内存、finite state、
pair-force residual、黏性功与拓扑门；判据完全来自预注册配置。

## 7. 子进程退出与资源回收

| run | return | PID | reclaimed | child RSS absent | parent RSS growth | scalar only | summary |
|---|---|---|---|---|---|---|---|
| stage01dp_canary_r1 | 0 | 27761 | True | True | 16384 | True | `06_experiments/stage_01dp_resource_policy/results/run_summaries/stage01dp_canary_r1.json` |
| stage01dp_canary_r2 | 0 | 28114 | True | True | 114688 | True | `06_experiments/stage_01dp_resource_policy/results/run_summaries/stage01dp_canary_r2.json` |
| stage01dp_canary_r3 | 0 | 28476 | True | True | 114688 | True | `06_experiments/stage_01dp_resource_policy/results/run_summaries/stage01dp_canary_r3.json` |

## 8. Canary 的证据边界

**本 canary 不属于 V2 收敛数据。** 未计算收敛率、误差阶或 GCI，也不得并入未来正式 V2 数据。

## 9. 唯一政策状态

唯一状态为 **`POLICY_PASS_ISOLATED_DEFAULT_GC`**。

| gate | name | passed | observed | required |
|---|---|---|---|---|
| P1 | read_only_evidence_identity | True | sha=5/5 r5_status=True | all identities and frozen R5 status |
| P2 | evidence_horizon | True | R5=2000 planned=1600 | R5 default-GC horizon >= planned maximum |
| P3 | maximum_horizon_canaries | True | 3/3 | 3/3 operational gates |
| P4 | subprocess_reclamation | True | reclaimed=True scalar=True parent_rss=True | 3/3 exited, no child RSS, scalar-only return, bounded parent |
| P5 | default_gc_no_grad_no_collect_policy | True | runs=3 | default GC enabled and no_grad for all canaries |
| STATUS | unique_policy_status | True | POLICY_PASS_ISOLATED_DEFAULT_GC | ["POLICY_CONDITIONAL_REDUCED_SCOPE","POLICY_EVIDENCE_INCOMPLETE","POLICY_FAIL_OPERATIONAL_ENVELOPE","POLICY_PASS_ISOLATED_DEFAULT_GC"] |

## 10. Stage 01D2 设计申请资格

当前结论：**具备提交下一轮审计、申请设计新 Stage 01D2 的资格**。Stage 01D2 未设计、未建立、未运行。

## 11. 历史状态

Stage 01D=`V2_FAIL`；Stage 01D-R=`RESOURCE_FAIL_LINEAR_GROWTH`；
Stage 01D-R2=`ATTRIBUTION_UNRESOLVED`；Stage 01D-R3=`R3_CONFIRMATION_UNRESOLVED`；
Stage 01D-R4=`R4_RETENTION_REDETECTED`；Stage 01D-R5=`R5_BOUNDED_GC_DELAY_CONFIRMED`。
全部保持不变。

## 12. V3 与 Stage 02

**V3 未开始，Stage 02 未开始。** 未训练神经网络或生成学习标签。

## 证据索引

| path | SHA-256 | bytes |
|---|---|---|
| `06_experiments/stage_01dp_resource_policy/configs/preregistered_resource_policy.yml` | 2d52fee73a2d30f91bef9156d6edab63be817cd04b16996cd3a476e191bfbf22 | 5009 |
| `06_experiments/stage_01dp_resource_policy/results/campaign_summary.json` | 10758f6ec3c7d6d4ae63f40b07f9fcab0ffa54a864db3b595cb2997abad3558f | 505 |
| `06_experiments/stage_01dp_resource_policy/results/evidence_identity.csv` | 3a006e0428fa1ac4ba24c8d14821a964c02048ac0040e9632d6745e70ae26c70 | 1253 |
| `06_experiments/stage_01dp_resource_policy/results/evidence_horizon.csv` | ab8d60c10f0e86d780d4e0f2337e71f648e2744c342f48beafca033849afc85f | 196 |
| `06_experiments/stage_01dp_resource_policy/results/canary_summary.csv` | f05175015e6b746ff04722496025d0513a0667e0e08cc53dc52765bc0717b31e | 988 |
| `06_experiments/stage_01dp_resource_policy/results/subprocess_audit.csv` | 78458bf68d01ca71617dc4e1b72c1b265b7b0b0337f495d7e6f90f18b0fa952e | 545 |
| `06_experiments/stage_01dp_resource_policy/results/policy_gate_evidence.csv` | fcb2c23b2fb5ab35f1156cf2e04d1696d156d1f471b87f610f5e46fcda1b2984 | 723 |
| `06_experiments/stage_01dp_resource_policy/results/analysis_summary.json` | 16049e8ddb4c68b8dd4c90d8e2a2506f6cdba1acbbaac1563c340b864fe85809 | 1060 |
| `06_experiments/stage_01dp_resource_policy/results/stage01dp_status.txt` | 0ca7cdd036635e044a828afe6100b5af1d28db5177bdb2ad26444c9419b4667f | 32 |
