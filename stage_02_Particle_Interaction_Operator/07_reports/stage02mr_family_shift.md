# Stage 02M-R — Family/configuration shift

基于允许输入的 graph summaries，validation 相对 train 的 NN/convex-hull 平均距离为 `12.262` / `11.984`；consumed test input 为 `6.829` / `6.432`。逐 resolution/support 结果已记录。

这些距离和已冻结的 validation/test metrics 仅作历史描述。由于 164 个 checkpoint 在 train 上从未达门，family shift 不是主要阻断因素。Test target decode=0，new test evaluations=0；BLIND_FAMILY_04 仍是 consumed historical test only。
