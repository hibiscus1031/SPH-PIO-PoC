# Stage 03B freeze and scope

唯一授权来自 Stage 03A `DYNAMIC_HYBRID_SOLVER_SPECIFICATION_COMPLETE`。Stage 03B 只实现和资格认定解析/MMS、同半离散 DOP853 与 source-free exact reference；不实现 D1/D2/D3、Transformer 或 temporal hidden network，不创建 optimizer/training、neural rollout、solver-in-the-loop、dataset split、normalization 或性能结论。

只读历史状态保持：Stage 01 `V2_QUALIFICATION_FAIL`；Stage 01H `FINITE_RESOLUTION_DOMINANT`；viscosity operator form `NOT_CONFIRMED`；Stage 02 static learning route `TERMINATED`。Stage 01 shear/acoustic 仅为 `historical_independent_evidence_only`，未被复制或重命名为新的 blind evidence。

输入冻结 manifest 对 Stage 03A、Stage 01F/F2、Stage 01G/H 和基线 SPH/EOS/kernel/graph 实现共 23 个 SHA-256 输入完成解析。正式环境为 CPU float64、4 threads、deterministic，域 `[-1,1)^2`，`L=2, rho0=1, cs=20, nu=0.02`，主路径 `H/dx=2.6`，输出 `tau=n/256, n=0,...,16`。
