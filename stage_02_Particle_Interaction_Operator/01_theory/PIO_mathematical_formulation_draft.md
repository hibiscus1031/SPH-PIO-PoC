# Particle Interaction Operator — Mathematical Formulation Draft

**状态：DRAFT / NON-EXECUTABLE**  
**范围：数学定义与约束；无 Transformer 实现、无参数、无训练、无数值运行。**

## 1. 粒子状态与邻域

在时刻 \(t\)，粒子 \(i\) 的状态记为

\[
\mathbf s_i=(\mathbf x_i,\mathbf v_i,\rho_i,p_i,m_i,h_i,\boldsymbol\eta_i),
\]

其中 \(\boldsymbol\eta_i\) 可容纳已冻结、可审计的无量纲物理量和数值元数据。邻域图 \(\mathcal G=(\mathcal V,\mathcal E)\) 由冻结 SPH 邻域规则构造。周期域中的 pair 几何使用 minimum-image 位移

\[
\mathbf r_{ij}=\operatorname{MI}(\mathbf x_j-\mathbf x_i),
\quad r_{ij}=\|\mathbf r_{ij}\|,
\quad \mathbf v_{ij}=\mathbf v_j-\mathbf v_i.
\]

PIO 不重新定义邻域，也不修改 baseline neighbor search。

## 2. Baseline、reference 与学习目标

冻结 SPH 加速度为

\[
\mathbf a_{\mathrm{SPH},i}=\mathcal A_{\mathrm{SPH}}(\{\mathbf s_k\},\mathcal G)_i.
\]

参考加速度必须在同一粒子状态上评价：

\[
\mathbf a_{\mathrm{ref},i}=\mathcal A_{\mathrm{ref}}(\{\mathbf s_k\})_i.
\]

唯一主标签为

\[
\Delta\mathbf a_i=\mathbf a_{\mathrm{ref},i}-\mathbf a_{\mathrm{SPH},i}.
\]

PIO 输出 \(\widehat{\Delta\mathbf a}_i\)，校正后加速度为

\[
\mathbf a_{\mathrm{corr},i}=\mathbf a_{\mathrm{SPH},i}+\widehat{\Delta\mathbf a}_i.
\]

因此零输出严格恢复原 SPH。PIO 不承担状态方程、质量守恒或时间积分器的替换。

## 3. 局部 particle-interaction 表示

候选局部输入分为三类：

- 节点标量：\(\rho_i,p_i,m_i,h_i\) 及无量纲组合；
- pair 标量：\(r_{ij}/H_{ij}\)、核值、核梯度径向系数、密度比、质量比、局部 Mach/Reynolds 指示量；
- pair 向量：\(\mathbf r_{ij}/H_{ij}\)、\(\mathbf v_{ij}/c_s\) 及其旋转等变组合。

抽象的邻域 Transformer 表述为

\[
\mathbf z_i=\operatorname{PIOEncoder}_\theta\left(
\mathbf s_i,
\left\{\mathbf e_{ij}:j\in\mathcal N(i)\right\}
\right),
\]

其中集合输入要求对邻居排列不敏感。当前草案不选择 attention 维数、层数、head 数、激活函数或参数量。

## 4. 守恒优先的 pairwise 输出

为控制总内力，优先研究 pair force correction，而不是直接输出无约束节点加速度。令无向 pair \(\{i,j\}\) 的候选修正为

\[
\Delta\mathbf F_{ij}=\Psi_\theta(\mathbf s_i,\mathbf s_j,\mathbf e_{ij}),
\qquad
\Delta\mathbf F_{ji}=-\Delta\mathbf F_{ij}.
\]

节点修正为

\[
\widehat{\Delta\mathbf a}_i=\frac{1}{m_i}
\sum_{j\in\mathcal N(i),j\ne i}\Delta\mathbf F_{ij}.
\]

则在封闭周期系统中

\[
\sum_i m_i\widehat{\Delta\mathbf a}_i=\mathbf 0
\]

由构造成立。一个可选的等变参数化是

\[
\Delta\mathbf F_{ij}
=\alpha_{ij}\,\widehat{\mathbf r}_{ij}
+\beta_{ij}\,\mathbf v_{ij}^{\perp r}
+\gamma_{ij}\,\mathbf v_{ij}^{\parallel r},
\]

其中 \(\alpha_{ij},\beta_{ij},\gamma_{ij}\) 为交换对称的标量函数，向量基随坐标旋转而旋转。是否保留非中心分量必须由未来角动量与耗散证据决定；当前不作资格声明。

## 5. 对称性和等变性合同

未来实现至少应满足：

1. **粒子置换等变**：重排粒子索引只重排输出；
2. **平移不变**：输入只使用相对位置或经明确中心化的绝对量；
3. **周期一致性**：跨边界 pair 使用 minimum-image 几何；
4. **旋转等变**：坐标和速度旋转时，修正加速度同样旋转；
5. **交换一致性**：pair 标量对 \(i,j\) 交换满足预定对称性，pair force 满足反对称性；
6. **零修正回退**：禁用 PIO 时逐位恢复 baseline SPH。

这些均是未来测试合同，不是当前已验证结果。

## 6. 参考层级与可辨识性

\(\mathbf a_{ref}\) 必须带 reference class：

- **R1 continuum-compatible**：解析 PDE/MMS 加速度，且连续模型与冻结 WCSPH 合同一致；
- **R2 semidiscrete-qualified**：高精度时间参考用于隔离 RK2 时间误差，不自动提供空间离散标签；
- **R3 independent benchmark**：用于外部验证，默认不进入训练；
- **RX model-form-misaligned**：连续模型与基线合同不一致，只能用于诊断，不能被标为纯 discretization correction。

标签资格要求参考不确定性 \(u_{ref,i}\) 相对目标足够小，例如未来可冻结

\[
u_{ref,i}\le\tau_{ref}\max(\|\Delta\mathbf a_i\|,a_{floor}),
\]

但 \(\tau_{ref}\) 和 \(a_{floor}\) 当前不赋值，以避免 preparation phase 发生参数调节。

## 7. 误差分解

对 trajectory-derived 量，应区分

\[
\mathbf e_{total}
=\mathbf e_{space}
+\mathbf e_{time}
+\mathbf e_{forcing}
+\mathbf e_{reference}
+\mathbf e_{model\ form}
+\text{cross terms}.
\]

PIO 主标签仅允许对应可归因的空间/粒子离散成分。若标签由不同时间积分器或不同连续模型直接相减得到，必须证明非目标项已隔离或足够小。

## 8. 未来目标函数草案

若未来获得训练授权，主误差可写为质量加权残差

\[
\mathcal L_{acc}
=\frac{\sum_i m_i\|\widehat{\Delta\mathbf a}_i-\Delta\mathbf a_i\|^2}
{\sum_i m_i\|\Delta\mathbf a_i\|^2+\varepsilon}.
\]

可能的辅助项包括总力残差、旋转/置换一致性、pair antisymmetry、耗散符号和跨分辨率一致性。当前不冻结权重，不定义 optimizer，也不执行训练。

## 9. 适用域与排除域

初始理论域限定为二维、周期、光滑、弱可压缩、低马赫、已验证核/支撑/分辨率范围。自由表面、固壁、冲击、多相、FSI、湍流和三维均排除。任何扩展必须重新定义参考、邻域和守恒门。

## 10. 开放问题

- 节点残差与 pair force residual 的表达能力差异；
- 非中心黏性修正的角动量/耗散折中；
- cutoff crossing 时 attention 集合变化的稳定性；
- density/EOS 不一致是否应进入标签或被资格门排除；
- 多参考层级之间是否需要独立模型或显式条件变量；
- 修正幅值限制和长期 rollout 稳定性证明。

## 11. 当前结论

本草案冻结了问题定义和科学边界，但没有冻结网络架构、训练损失权重或数据参数。其状态仅为 `PIO_FORMULATION_DRAFT_COMPLETE`，不代表理论资格或模型实现完成。
