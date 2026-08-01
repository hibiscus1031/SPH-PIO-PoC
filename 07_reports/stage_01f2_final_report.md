# Stage 01F2 final report

## 1. Stage 01F 冻结

Stage 01F 的 `153c1d2` 预注册、`f835b05` 最终证据、`MMS_SPECIFICATION_PASS` 状态及 9 项 SHA-256 manifest 全部通过。Annotated tag `stage-01f-mms-specification-pass` 指向 `f835b05`；Stage 01F 原文件未修改。

## 2. Source adapter 实现

新增纯函数只接受 solution id、当前 numerical positions、physical stage time 和冻结参数，直接调用 Stage 01F 解析 source。它不读取残差/误差/未来状态、不改变输入、不缓存历史，输出单位质量外部加速度并保持 float64 CPU autograd。

## 3. RK2 start/midpoint 注入

保留 explicit midpoint RK2。每步 start 在 `x_n,t_n` 重算，midpoint 在 numerical `x_mid,t_n+dt/2` 重算；无 endpoint 第三次施加。六条轨迹的每一步均严格记录两次调用，内部 pair result 未包含 source。

## 4. Source-disabled 回归

N16 zero-flow、N16 20-step TGV、N32 20-step TGV 均为 bitwise equality；状态最大绝对差为 0，edge identity、force identity、邻域构建次数和持久 tensor schema 保持不变。

## 5. MMS-A 闭式参考

使用 `x0+U_c t,y0` 的 continuous unwrapped 闭式轨迹，场评价时 wrap；指定时间、周期穿越和双向最小像测试全部通过，未用数值积分生成。

## 6. MMS-B DOP853 参考与敏感性

N16/N32 baseline 与 tighter 参考最大差为 0，与 half-max-step 最大差为 `6.66e-16`。所有参考 finite，初始位置 bitwise identity，元数据包含参数 hash、积分器、容差、maximum step 与代码提交。

## 7. 固定质量初始化

MMS-A/B 的 N16/N32 均使用 `m_i=rho_exact(x_i^0,0)(2/N)^2`，总质量精确为 4；masses 固定。numerical density 只由 SPH kernel sum 产生，analytic density 未覆盖数值密度。结果与 Stage 01F particle-initialization 证据 hash 身份一致。

## 8. Internal/external balance

最大 `F_total-(F_internal+F_external)` 范数为 `4.62e-16`，最大 midpoint 动量更新缺陷为 `1.42e-17`。pair-force residual 最大为 0，normalized internal-force residual 和 viscous power 全部通过冻结门。

## 9. A1/A2/B1/B2 短程动态结果

所有状态和参考 finite，topology defects 为 0，最小 `separation/dx=0.9399`。最终 velocity relative L2 最大 `9.30e-3`，density relative L2 最大 `4.22e-4`，position relative L2 最大 `3.40e-5`。这些数值仅用于实现灾难检测。

## 10. Source AD/FD

numerical x/y、physical time 及全部规定参数的预期非零梯度 finite 且非零，并逐项与中心有限差分比较；最大相对差 `4.08e-10`，通过 `1e-5` 门。正式前向使用 `torch.no_grad()`，无跨步 graph。最终判定采用强化后的 v2 AD/FD 证据。

## 11. 资源和确定性

最高 current/peak RSS 分别约 370.7/370.7 MB，最大 RSS 四分位绝对增长约 19.4 MB，相对增长约 5.59%，最差 step-time Q4/Q1 为 1.014。全部子进程完全回收，parent 接收 scalar-only summary。A2 和 B2 的独立 checkpoint 均 bitwise equality。

## 12. 证据边界

本阶段证据仅允许称为 implementation smoke、code-path verification、deterministic repeat、reference sensitivity 与 balance audit。未执行正式时间或空间精度研究，未生成任何后续资格数值。

## 13. 唯一 Stage 01F2 状态

**MMS_IMPLEMENTATION_VERIFIED_PASS**

## 14. Stage 01F3 申请资格

具备提交下一轮审计、申请设计 Stage 01F3 的资格；本阶段未自动启动 Stage 01F3。

## 15. Stage 01D2 历史状态

Stage 01D2 的历史失败状态保持不变，未追溯修改或重新分类。

## 16. 后续边界

V3 与 Stage 02 仍未开始；未训练 MLP、Transformer 或 attention，未生成学习标签。工作在 Stage 01F2 完成后停止。
