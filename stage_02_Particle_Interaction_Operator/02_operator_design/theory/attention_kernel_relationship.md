# Attention 与 SPH kernel 的理论关系

## 1. 冻结表述

SPH kernel 提供由连续核、平滑长度、支撑和离散求和合同确定的 **fixed physical interaction
weighting**。Attention 若在未来被采用，只能提供依赖局部状态的 **learned interaction weighting**。
PIO 的关系因此冻结为：

> PIO is a learned correction over a validated physical interaction; attention does not replace the SPH kernel.

## 2. 数学映射而非等价替换

冻结 SPH pair 项可抽象为

\[
a_{\mathrm{SPH},i}=\sum_{j\in\mathcal N(i)}
w^{\mathrm{SPH}}_{ij}(r_{ij},h_i,h_j,\rho_i,\rho_j,\ldots)\,q^{\mathrm{SPH}}_{ij},
\]

其中 \(w^{\mathrm{SPH}}_{ij}\) 的来源是已冻结物理/数值合同。未来 attention 可抽象为在同一合格图上的
状态依赖系数 \(\alpha_{ij}\)，但它只能参与残差通道，例如

\[
\Delta F_{ij}=\Phi\!\left(alpha_{ij},e_{ij};w^{\mathrm{SPH}}_{ij},q^{\mathrm{SPH}}_{ij}\right),
\qquad
a_{\mathrm{corr},i}=a_{\mathrm{SPH},i}+\frac{1}{m_i}\sum_j\Delta F_{ij}.
\]

该式只是功能角色映射，不冻结 \(\Phi\) 或 attention 实现。

## 3. 不允许的推论

- 不能从 \(\alpha_{ij}\) 的存在推断 learned kernel 具有 SPH kernel 的一致性、归一性或守恒性质；
- 不能用 attention 权重替换 kernel 后仍称 baseline 未改变；
- 不能把 softmax 归一化等同于 partition of unity、核矩条件或 pair-force 反对称性；
- 不能用 attention 可视化作为物理机制或误差归因证据；
- 不能让 attention 改写邻域图或掩盖 topology failure。

## 4. 未来资格要求

若 Stage 02 后续采用 attention，必须独立证明/测试：邻居排列不敏感、pair 交换合同、minimum-image 一致性、
旋转等变、cutoff crossing 下的定义完备性、零修正回退，以及 pair 聚合后的守恒。任何这些性质都不由
“使用 attention”自动得到。
