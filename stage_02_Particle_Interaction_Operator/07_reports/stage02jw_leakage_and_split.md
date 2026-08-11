# Stage 02J-W Leakage and Split

Lineage registry 含 4 个互相独立 family。每族 5 个 configuration records 构成一个 component，不同 family 无共享 seed、formula ancestry、restart、resample 或 direct lineage。共享 EOS/SPH/Fourier/serializer/domain 不视为 lineage。

Leakage graph 恰有 4 个 disconnected components，cross-family edges=0。冻结 family split 为 train 10、validation 5、test 5；无 cross-split path，未采用 particle/edge/patch 或 resolution/support 伪独立 split。


边界声明：本阶段没有模型实现、Transformer、attention、优化器、训练、验证/测试性能评价或 benchmark claim。Stage 01 `V2_QUALIFICATION_FAIL`、`FINITE_RESOLUTION_DOMINANT` 与 viscosity operator form `NOT CONFIRMED` 均未改变。
