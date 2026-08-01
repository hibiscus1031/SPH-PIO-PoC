# Stage 01D-P Resource Policy

## 运行解释

R5 表明 GC-disabled 路径线性累积，而默认 GC 的 2000-step 上包络有界。
本政策把资源安全裁决放在最大单轨迹能否在明确 RSS、时间、数值、拓扑及进程回收边界内完成，
不要求 retired count 每步为零、后半程必有全量归零，也不要求 live tensor 原始斜率严格为零。

## 冻结政策

正式运行政策固定为：每条轨迹一个独立子进程；默认 cyclic GC 启用；
前向处于 `torch.no_grad()`；不在时间循环中调用 `gc.collect()`，也不关闭 cyclic GC；
父进程不接收 Tensor、neighborhood 或完整 state；只保留标量 diagnostics 与相对证据路径；
轨迹结束即退出子进程；AD 检查必须使用另一短程进程。

## 裁决门

| gate | name | passed | observed | required |
|---|---|---|---|---|
| P1 | read_only_evidence_identity | True | sha=5/5 r5_status=True | all identities and frozen R5 status |
| P2 | evidence_horizon | True | R5=2000 planned=1600 | R5 default-GC horizon >= planned maximum |
| P3 | maximum_horizon_canaries | True | 3/3 | 3/3 operational gates |
| P4 | subprocess_reclamation | True | reclaimed=True scalar=True parent_rss=True | 3/3 exited, no child RSS, scalar-only return, bounded parent |
| P5 | default_gc_no_grad_no_collect_policy | True | runs=3 | default GC enabled and no_grad for all canaries |
| STATUS | unique_policy_status | True | POLICY_PASS_ISOLATED_DEFAULT_GC | ["POLICY_CONDITIONAL_REDUCED_SCOPE","POLICY_EVIDENCE_INCOMPLETE","POLICY_FAIL_OPERATIONAL_ENVELOPE","POLICY_PASS_ISOLATED_DEFAULT_GC"] |

唯一状态为 **`POLICY_PASS_ISOLATED_DEFAULT_GC`**；具备提交下一轮审计、申请设计新 Stage 01D2 的资格。该资格不等于已设计或运行 Stage 01D2。
