# Stage 01F5-P 扩展执行 Manifest

## 矩阵身份

`stage01f5_execution_run_matrix_v2.csv` 的前 64 行与原 Stage 01F5 矩阵逐字段、逐顺序一致。补充 manifest 记录了原矩阵整体 SHA-256 和 64 个数据行各自的 SHA-256，未重命名任何原 run ID。

扩展矩阵新增五条条件行：两条 N64 smoke 与三条 MMS-B N64 reference。新矩阵为 62 条无条件计划、7 条条件计划、共 69 行；69 个 run ID 和 69 个未来输出目录均唯一。扩展矩阵 SHA-256 为 `ebbfa5fd3ffced88d1995fc34000b4e1a25524cb93d23e9d6fd9b9a4c4ab061b`。

## Smoke 条目

`f5_n64_smoke_a` 与 `f5_n64_smoke_b` 固定使用 N64、4096 粒子、`H/dx=6.041381265149109` 和已提交 `space_step_decision.json` 中的 `dt_space`，各运行 20 步，`t_final_smoke=20*dt_space`。Smoke 不进入正式空间误差序列。

未来 smoke 必须检查 finite、每步 start/midpoint source、力/组装/动量、黏性、最小间距、reciprocal topology、零 structural defects、current/peak RSS、子进程回收与预计正式 wall time。

## MMS-B N64 reference 条目

三条 ID 已分配为 baseline/tighter/third，并继承 Stage 01F5 的 DOP853 容差、max_step、production sparse RHS、unwrapped positions、topology、sensitivity、10-state sparse/dense 抽查和按字段/范数 reference uncertainty 要求。

然而 formal-space `t_final` 未在冻结 `spatial_matrix` 或原矩阵中明确给出。本审计不得以 N20 或 held-out 的 `0.015` 代填。三条 reference 因而是结构上已分配、参数上仍被阻断的条件行，不能执行。

## 不变项

N20 主配置、N28 held-out、T1–T5、P1–P3、H1–H5、S1–S4、N64 triggers、资源与安全门、DOP853 容差均未改变。扩展只为既有协议所需的五个条件依赖分配 ID 和输出目录。
