# Stage 01E — TGV benchmark alignment

令 `k=pi`、`A=exp(-2 nu k^2 t)`。速度与解析压力按预登记式实现。显式结果为：`partial_t u=-2 nu k^2 u`；`(u·grad)u=(U0^2 A^2 k/2)[sin(2kx),sin(2ky)]`；`-grad(p)/rho0` 等于同一对流项；`nu laplacian(u)=-2 nu k^2 u`。因此 `D u/Dt=-grad(p)/rho0+nu laplacian(u)`。随机坐标 float64 测试见 `test_stage01e_exact_tgv_pressure.py` 与 `test_stage01e_material_acceleration.py`，完整 pytest 为证。

这揭示 benchmark alignment：不可压 TGV 在 t=0 需要非零空间压力场，而冻结 WCSPH 初始化压力来自 `c_s^2(rho_h-rho0)`；两者并不自动相容。
