# Stage 01D-R3 Frozen-topology Control F

## 控制定义

F 使用 N32 zero-flow、H/dx=5.0，只在初始状态建立一次 reciprocal、duplicate-free
edge index，后续 2000 步固定该 index。density、EOS、pressure、viscosity 与 RK2
仍调用冻结的项目算子；F 只用于资源归因。

## 三次独立子进程

| run | steps | edge values | edge IDs | tensor Δ | unknown Δ | old bytes | age-2 | margin | PASS |
|---|---|---|---|---|---|---|---|---|---|
| stage01dr3_f_r1 | 2000 | 1 | 1 | 0 | 0 | 0 | 15 | 0 | False |
| stage01dr3_f_r2 | 2000 | 1 | 1 | 0 | 0 | 0 | 15 | 0 | False |
| stage01dr3_f_r3 | 2000 | 1 | 1 | 0 | 0 | 0 | 15 | 0 | False |

三次均完成，edge count 与 edge identity 各只有一个值；old-survivor、unknown
growth、same-slot history 和 referrer chain 均为零。但三次的最大 age-2 weakrefs
均为 `15`，不满足预登记的零门槛，因此 T2=False。由于这些引用的 storage
仍属于当前固定拓扑工作集，old-survivor storage/bytes 为零；这不是旧 storage
累积证据，但仍阻止本轮确认。
