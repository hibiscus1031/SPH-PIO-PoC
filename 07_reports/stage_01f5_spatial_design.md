# Stage 01F5 空间验证设计

## 空间时间步隔离

未来首先且只在 N32、`H/dx=5.049509756796392` 上运行四条隔离轨迹：

- MMS-A：`f5_space_iso_a_dt6p25e5`、`f5_space_iso_a_dt3p125e5`；
- MMS-B：`f5_space_iso_b_dt6p25e5`、`f5_space_iso_b_dt3p125e5`。

比较 position、velocity、density、pressure 的 endpoint L2。若任一字段相对变化大于 0.10，`dt_space=3.125e-5`；否则 `dt_space=6.25e-5`。选择必须在正式 N16/N24/N48 运行前写入并提交 immutable decision 文件，查看空间趋势后不得改变。

## 正式 consistency path

| N | particle count | H/dx |
|---:|---:|---:|
| 16 | 256 | 4.06155281280883 |
| 24 | 576 | 4.5 |
| 32 | 1024 | 5.049509756796392 |
| 48 | 2304 | 5.5 |
| 64（条件） | 4096 | 6.041381265149109 |

MMS-A 正式 ID 为 `f5_space_a_n16/n24/n32/n48`，MMS-B 为 `f5_space_b_n16/n24/n32/n48`。S1–S4 要求八条主轨迹完成并通过硬安全门；每个 MMS、每个字段均满足 N48 优于 N16、N16→N24→N32→N48 严格下降、global log(error)-log(dx) slope 为正。

结果只能称为 `increasing-neighbor consistency-path convergence`，不得称为 fixed-stencil single-h convergence。

## 条件 N64

任一主误差在 N16–N48 非单调、任一 N48/N32 比大于 0.95、局部阶符号不一致或近渐近区不清楚时，触发 `f5_space_a_n64` 与 `f5_space_b_n64`。运行前必须完成 20-step smoke，并同时满足 peak RSS `<2 GB`、预计单条 wall time `<2 h`、cutoff margin `>1e-12`、structural topology defects `=0`。一旦启动，不得删除不利结果。

## Observed order 与 GCI

GCI 按变量独立资格化。必须同时具有至少三个连续严格单调误差、局部阶同号、相邻局部阶相对差不超过 25%、误差高于 reference/time-step floor 20 倍、合法三点子序列变化不超过 25%，且 extrapolated value finite。否则写 `GCI not justified`。

若可计算，必须声明：`GCI applies only to the preregistered increasing-neighbor consistency path and is not a fixed-stencil single-h GCI.` 不得跨变量共享 GCI。本次不要求运行 fixed-ratio family；旧 fixed-ratio 数据只能作背景。
