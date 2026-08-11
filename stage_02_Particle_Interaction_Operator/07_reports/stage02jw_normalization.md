# Stage 02J-W Normalization

Normalization 仅在 20 records、4 components 与 split 全部 PASS 后拟合。输入严格为 BLIND_FAMILY_01/02 的 10 个 train full graphs，并采用 `equal_weight_per_complete_graph; population second moment; componentwise`。

统计覆盖 position/domain、displacement/h、distance/h、velocity/cs、density deviation/rho0、pressure/(rho0 cs^2)、h/domain 与 mass/(rho0 domain area)。validation、test、历史 PV/CROSSMODE/DIAGONAL/MIXED、jitter、target、reference 和 target-derived quantities 全部排除。statistics hash: `sha256:2208d2f4b9b7c848f2cd1b93624f9f6a3d9fb29e65cdd70ee453e6122c43d051`。


边界声明：本阶段没有模型实现、Transformer、attention、优化器、训练、验证/测试性能评价或 benchmark claim。Stage 01 `V2_QUALIFICATION_FAIL`、`FINITE_RESOLUTION_DOMINANT` 与 viscosity operator form `NOT CONFIRMED` 均未改变。
