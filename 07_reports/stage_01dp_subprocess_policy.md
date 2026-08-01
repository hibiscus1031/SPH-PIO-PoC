# Stage 01D-P Subprocess Policy Audit

正式运行政策固定为：每条轨迹一个独立子进程；默认 cyclic GC 启用；
前向处于 `torch.no_grad()`；不在时间循环中调用 `gc.collect()`，也不关闭 cyclic GC；
父进程不接收 Tensor、neighborhood 或完整 state；只保留标量 diagnostics 与相对证据路径；
轨迹结束即退出子进程；AD 检查必须使用另一短程进程。

父进程顺序启动三个 canary：

| run | return | PID | reclaimed | child RSS absent | parent RSS growth | scalar only | summary |
|---|---|---|---|---|---|---|---|
| stage01dp_canary_r1 | 0 | 27761 | True | True | 16384 | True | `06_experiments/stage_01dp_resource_policy/results/run_summaries/stage01dp_canary_r1.json` |
| stage01dp_canary_r2 | 0 | 28114 | True | True | 114688 | True | `06_experiments/stage_01dp_resource_policy/results/run_summaries/stage01dp_canary_r2.json` |
| stage01dp_canary_r3 | 0 | 28476 | True | True | 114688 | True | `06_experiments/stage_01dp_resource_policy/results/run_summaries/stage01dp_canary_r3.json` |

campaign 汇总：process reclaimed=`True`，child RSS absent=
`True`，scalar-only return=`True`，
maximum parent RSS growth=`114688` bytes。
