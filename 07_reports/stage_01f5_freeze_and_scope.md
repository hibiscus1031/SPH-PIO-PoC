# Stage 01F5 冻结与范围

## Stage 01F4 冻结

Stage 01F4 最终证据提交固定为 `82de6171a0be9818303acca539bffc8d3ee21c22`，唯一状态为 `PLATEAU_AWARE_PROTOCOL_APPROVED`。Annotated tag `stage-01f4-plateau-aware-protocol-approved` 精确指向该提交。

Stage 01F3C 的 annotated tag `stage-01f3c-ct2-mixed-or-unresolved` 仍指向 `f831d4fa7d63ad3357e2b1e84c1260d7f3c46a2e`。历史状态保持：Stage 01F3B 为 `MMS_CONVERGENCE_VERIFICATION_FAIL`，Stage 01F3C 为 `CT2_MIXED_OR_UNRESOLVED`。

Stage 01F4 的最终报告、旧 CT2 审计、plateau-aware 指标、前瞻性协议、预注册配置、evaluator 和 Stage 01F3C 冻结 manifest 共 7 项 SHA-256 全部复核通过。

## 本阶段授权范围

Stage 01F5 只冻结一次未来重资格设计。本阶段没有导入或调用动态 solver，没有调用 RK2 或 SciPy DOP853，没有生成 reference NPZ，没有执行时间或空间收敛，没有生成轨迹、训练产物或学习标签。

机器可读运行矩阵中的方法、参数和输出目录都是未来 Stage 01F5B 的计划记录，不是已经执行的作业。Stage 01F5B、Stage 01G、V3 和 Stage 02 均未启动。

## 历史数据隔离

Stage 01F3B/F3C 轨迹只能作为设计背景，不能作为 N20 主配置、N28 held-out 或新空间矩阵的误差点、重复、参考或通过证据。Stage 01F4 的 T1–T5 和 P1–P3 原样冻结；不增加百分比容差解释旧 CT2。
