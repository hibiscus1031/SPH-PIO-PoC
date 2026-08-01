# Stage 01F2 autograd and determinism

source 对 numerical x、numerical y、physical time、`epsilon_rho`、`U_c`、`U_v` 和 `lambda` 的预期非零梯度均 finite 且非零。上述全部变量均与中心有限差分逐项比较，最大相对差为 `4.0766641599707824e-10`，通过 `1e-5` 门。权威证据为 `source_ad_fd_v2.csv` 与 `source_ad_fd_v2_summary.json`。

正式动态前向均位于 `torch.no_grad()` 中，source adapter 无历史缓存，未建立跨 accepted step 的持久 graph。

A2 两个独立 checkpoint 的 positions、velocities、densities、pressures、masses 逐数组 bitwise equality；B2 同样通过。所有 campaign 子进程回收后 RSS 为 0，parent 只接收标量 summary 与相对路径。

结论：source AD/FD 与 deterministic repeat 均 **PASS**。
