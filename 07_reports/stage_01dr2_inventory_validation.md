# Stage 01D-R2 Tensor Inventory 自验证

## 冻结与目的

Stage 01D-R 诊断协议提交为 `0d562a4d8ed662c33797b738cd0f7ae9c00c1618`，最终证据提交为 `3f5d2d5033cfadd559cc278c4f828b40bc40d324`。Annotated tag `stage-01dr-resource-fail-live-bytes-gate` target 为 `3f5d2d5033cfadd559cc278c4f828b40bc40d324`。旧状态 `RESOURCE_FAIL_LINEAR_GROWTH` 与 Stage 01D 的 `V2_FAIL` 均未修改。

本报告只验证测量器；Control A 不调用 solver。固定 Tensor 集合包含 base、两个 view
和独立 storage，生产 inventory 连续调用 1000 次，每次删除局部结果、执行
`gc.collect()`，再进行独立轻量计数。

## 三次独立子进程结果

| run | iterations | tensor Δ | storage Δ | fixture tensors | unique storages | PASS |
|---|---|---|---|---|---|---|
| stage01dr2_a_r1 | 1000 | 0 | 0 B (0.000 MB) | 4 | 2 | True |
| stage01dr2_a_r2 | 1000 | 0 | 0 B (0.000 MB) | 4 | 2 | True |
| stage01dr2_a_r3 | 1000 | 0 | 0 B (0.000 MB) | 4 | 2 | True |

storage key 明确采用 `(device, data_ptr, nbytes)`；base 与 view 只计一次。
`inventory_results_globally_retained=false`，正式结果不保存 Tensor 对象或 storage。

## 判定

Inventory gate 为 **PASS**。
若该 gate 失败，协议要求停止 B/C/D 并选择 `INVENTORY_INSTRUMENTATION_BIAS`。
