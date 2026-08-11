# Stage 02M-R — Failure attribution

唯一主归因：**STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING**。

证据闭合：basis 的自由 per-edge representability 仍为 PASS（源 hash `sha256:fde75cae5457ef4a3a2ff7cb06adcbf5d6c554d6cdff077ad7b0447444737b67`），但它不证明 learned map；未发现 hard feature contradiction；K1 有 2 个 selected seeds 的 head tangent 可达 train gate，而历史实际为 0/3；normalized target/loss 和 Adam/WD/gradient 证据支持条件化不良。Selection/transfer 条件因历史 train 从未达门而不成立；early stopping 不是主要阻断；whole-network iteration-limited LSQR 不能支持 function-class limit。

本归因不等于新模型性能，不宣称 attention 必要、K2 优于 K1、Stage 01 恢复，也不授权训练或 rollout。
