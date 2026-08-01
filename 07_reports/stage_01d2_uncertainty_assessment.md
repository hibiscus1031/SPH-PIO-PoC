# Stage 01D2 numerical uncertainty assessment

1. 时间离散误差：四个 dt 的解析 endpoint 与共同时间 self-difference 联合评估；time=PASS。
2. 空间离散误差：N16/N24/N32 与两种 support family 分开；space=PASS。
3. 弱可压模型形式：用 c_s=10/20/40 定量，不将其混入空间误差。
4. 粒子无序：六个冻结 jitter 种子仅为有限稳健性证据；状态 `D_FAIL`。
5. 支撑尺度：constant/increasing 家族差异单独列表。
6. float64 舍入：残差门附近的数值只解释为舍入容限内证据。
7. CPU 确定性：正式 backend 固定 CPU，seed 与 run ID 预登记。
8. GC：默认 cyclic GC 仅是资源运行条件，不属于物理误差。

结论：**GCI not justified**。解析参考误差包含时间、空间、弱可压与其他模型形式成分，未全部归因为空间离散。
