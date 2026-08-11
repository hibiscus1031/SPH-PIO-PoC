# Stage 02M-P — Train-only supervision scale

严格使用 10 个完整 train graphs、CPU float64、deterministic Kahan 和等图权计算：

`a_sup = 0.392220124168075 m s^-2`

结果 hash `sha256:85d5339dde02c29dba5bfa753096ab25598bd29a5df576def7691dcdbfef838e`，10 个 target-array hashes 和逐图能量均已保存。Historical validation/test target decode count 均为 0。a_sup 仅用于 output/supervision loss scaling，不作为输入特征、family ID 或 input normalization；旧 input-normalization hash仍为 `sha256:2208d2f4b9b7c848f2cd1b93624f9f6a3d9fb29e65cdd70ee453e6122c43d051`。
