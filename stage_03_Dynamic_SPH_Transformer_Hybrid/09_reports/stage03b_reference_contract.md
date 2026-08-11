# Stage 03B reference contract

公共粒子布局为 N=8×8、12×12、16×16 的等质量规则材料点。17 个时刻共同构成一条完整短轨迹，不能解释成 17 个 IID 样本。所有 record 的角色为 `audit_reference_trajectory_records`，没有 split、normalization、neural target、learned correction 或 optimizer state。

D-R1 Route 1 由冻结 SymPy closed-form material map 构造；Route 2 从 primitive map 使用独立 PyTorch float64 automatic differentiation。空间导数使用 `D_x,a g=sum_A(F^{-1})[A,a] partial_XA g`，并独立形成 `grad_x p`、`laplacian_x u` 和 source。

D-R2 状态含独立 `x,v,rho`，每个 RHS 重新构建 reciprocal graph，计算冻结 continuity、pressure、viscosity 和 EOS，再加入按固定材料标签与物理时间评价的 exact MMS external source。DOP853 只具有 `same_semidiscrete_time_reference` 身份，不是 spatial/continuum/high-fidelity truth。

D-R3 两个 oblique shear family 永久隔离为 `independent_source_free_validation_only`，禁止进入 training、normalization、threshold 或 architecture selection。
