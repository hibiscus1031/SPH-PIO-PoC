# Stage 01F3-R topology event 审计

## 方法

只读重放 Stage 01F3 的 MMS-B baseline DOP853 轨迹。先在相邻保存时刻识别每个无序粒子对的支撑内外变化，再对真实周期最小像距离二分求 `r/H=1` 事件时刻；在根两侧评价 dense pair contribution、dense 聚合 RHS，并由生产 sparse 邻域直接确认正反向边是否同步切换。没有要求 baseline/tighter 的内部 RHS 评价点一致。

## 结果

- 无序 cutoff 事件：216（加入 136，移除 80）。
- 事件时间范围：`0.00563209–0.00998325`。
- 根两侧评价点距 `q=1` 的最大偏差：`2.702e-11`。
- reciprocal 切换：216/216；每个事件的 `(i,j)` 与 `(j,i)` 同步。
- 保存轨迹全部结构缺陷最大值：0。
- 单边 pressure+viscosity 加速度贡献最大值：`1.964e-52`。
- 事件根两侧聚合 total RHS Linf 差最大值：`7.950e-10`；这是两个极近但不同物理时刻的平滑状态变化，低于 `1e-6` 审计门，且远大于单边 cutoff contribution 的事实排除了有限边跳跃。

所有粗时间区间均 bracket `q=1`，所有精化评价点均位于 cutoff 附近。事件表逐行保存 particle ids、时间区间、`r/H`、pressure/viscosity/total pair contribution、聚合 RHS 差及 reciprocal 状态。

唯一结果：**PASS**。证据：`06_experiments/stage_01f3r_reference_qualification/results/topology_events.csv` 与 `topology_event_summary.json`。
