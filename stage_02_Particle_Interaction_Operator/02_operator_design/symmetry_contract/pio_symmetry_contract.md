# PIO Symmetry / Equivariance 合同

## 1. 变换记号

令置换为 \(\pi\)，平移为 \(c\)，旋转为 \(Q\in SO(d)\)，周期晶格为 \(L\)。标量物理量在刚体变换下
不变，位置和极向量按 \(x'_i=Qx_i+c\)、\(v'_i=Qv_i\)、\(a'_i=Qa_i\) 变换。对周期问题，完整变换
同时要求 \(L'=QL\)。

## 2. 六项硬合同

### S1 粒子置换等变

\[
\widehat{\Delta a}(\pi\mathcal S,\pi\mathcal G)=
\pi\widehat{\Delta a}(\mathcal S,\mathcal G).
\]

粒子索引不得作为物理特征；邻居聚合不得依赖未声明的输入顺序。

### S2 平移不变

\[
\widehat{\Delta a}(\{x_i+c,v_i,\ldots\},\mathcal G)=
\widehat{\Delta a}(\mathcal S,\mathcal G).
\]

位置通道只能使用 minimum-image 相对几何，或具有等价证明的中心化表示。

### S3 周期 minimum-image 一致

对任意晶格向量 \(Lk_i\)，单独重映射粒子代表元不得改变物理输出：

\[
x_i' = x_i+Lk_i
\quad\Longrightarrow\quad
\widehat{\Delta a}'_i=\widehat{\Delta a}_i.
\]

图构造、pair 特征与 hash 必须使用同一 minimum-image/tie-breaking 合同。cutoff crossing 允许改变 edge identity，
但 reciprocal status 和拓扑缺陷必须记录；不要求跨状态 edge identity 恒定。

### S4 旋转等变

当状态与周期晶格共同旋转时，

\[
\widehat{\Delta a}(Q\mathcal S,Q\mathcal G;QL)=
Q\widehat{\Delta a}(\mathcal S,\mathcal G;L).
\]

若周期盒 \(L\) 固定，则只要求属于该晶格点群、保持盒子的旋转；任意角旋转需要同时旋转盒子。该限定防止
把矩形周期边界的几何变化误判为算子失配。反射 \(O(d)\) 等变不是本阶段默认声明。

### S5 Pair exchange symmetry

交换 \(i,j\) 时 \(r_{ji}=-r_{ij}\)、\(v_{ji}=-v_{ij}\)，并要求

\[
\Delta F_{ji}=-\Delta F_{ij}.
\]

一种充分而非唯一的构造，是由交换对称的标量系数乘以交换反对称、旋转等变的向量基。对有向边分别预测
但不作结构约束，不能视为满足此合同。

### S6 零修正回退

\[
\widehat{\Delta a}=0\quad\Longrightarrow\quad a_{\mathrm{corr}}=a_{\mathrm{SPH}}.
\]

未来测试必须比较冻结 RHS，不以“短 rollout 看起来相同”替代逐状态恒等检查。

## 3. 动态邻域合同

邻域 \(\mathcal G(\mathcal S)\) 是状态的分段变化函数。Stage 02 不假设 edge identity 恒定，也不声称 cutoff
处可微。合法 reciprocal cutoff crossing 不是 failure；duplicate、nonreciprocal、strict-support omission 与
unexpected exterior edge 是结构 failure。每个未来状态必须记录 neighbor graph hash、topology defects 与
reciprocal status。

## 4. 未来测试生成器要求

同一基础状态应生成置换、统一平移、周期代表元重映射、允许的旋转、pair 交换和零输出六组 metamorphic
cases。比较时必须重新构造应当变化的动态图，而不能强行复用旧 edge identity。阈值、随机种子与样本矩阵
由 Stage 02B 冻结；本文不执行测试。
