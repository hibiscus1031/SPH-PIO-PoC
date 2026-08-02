# Stage 01F5-Q 参数绑定

## 31 条正式空间绑定

`stage01f5q_space_parameter_binding.csv` 对 31 个唯一 run ID 绑定 `formal_space_t_final=0.02` 和同一个 21 点 `formal_space_common_times.csv`：

- 空间时间步隔离 4 条；
- N16/N24/N32/N48 正式空间轨迹 8 条；
- 空间 N32 确定性重复 2 条；
- MMS-B N16/N24/N32/N48 三层连续参考 12 条；
- 条件 N64 正式轨迹 2 条；
- 条件 MMS-B N64 三层参考 3 条。

绑定不增加、不删除、不重命名任何 run ID。Stage 01F5-P 的 69 行 v2 矩阵保持原样，参数通过独立 Stage 01F5-Q binding 层解析。

## 明确排除

N20 主时间矩阵、N28 held-out、主/held-out 半离散参考以及 `f5_n64_smoke_a/b` 不绑定 formal-space 时域。N20 与 N28 继续使用 `t_final=0.015` 和 16 个共同时间。

## N64 smoke 独立合同

两条 smoke 保持 20 步。若 `dt_space=6.25e-5`，则 `t_final_smoke=0.00125`；若 `dt_space=3.125e-5`，则 `t_final_smoke=0.000625`。Smoke 不使用 21 个正式空间共同时间，也不进入正式空间误差序列。

## 解析优先级

参数解析严格按：运行行显式参数 → Stage 01F5-Q binding → 原冻结配置 → 禁止隐式默认或推断。31 条绑定、共同时间与 amendment 配置均有独立 SHA-256。
