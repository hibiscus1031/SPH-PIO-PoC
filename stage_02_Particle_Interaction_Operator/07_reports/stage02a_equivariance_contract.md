# Stage 02A — Equivariance Contract 报告

规范合同见 `../02_operator_design/symmetry_contract/pio_symmetry_contract.md`。

## 六项冻结合同

1. **Particle permutation equivariance**：重排粒子只重排输出，粒子索引不得成为物理特征。
2. **Translation invariance**：统一平移不改变修正，位置输入使用 minimum-image 相对几何。
3. **Periodic minimum-image consistency**：改变粒子的周期代表元不改变输出；图、特征与 hash 共用 MI
   convention。
4. **Rotation equivariance**：状态和周期晶格共同按 \(Q\in SO(d)\) 旋转时，输出按 \(Q\) 旋转；固定盒仅
   要求其晶格点群旋转。
5. **Pair exchange symmetry**：交换 \(i,j\) 后 \(\Delta F_{ji}=-\Delta F_{ij}\)。
6. **Zero correction fallback**：\(\widehat{\Delta a}=0\) 时逐状态严格恢复 \(a_{\mathrm{SPH}}\)。

## 动态邻域限定

Stage 02A 不假设 edge identity 随状态恒定，也不声称 cutoff 处拓扑可微。合法 reciprocal cutoff crossing
允许改变邻居集合；未来 metamorphic test 必须按变换后的状态重新构图，同时审计 reciprocity 与结构缺陷。

## 理论参数化要求

满足交换对称的标量系数与交换反对称、旋转等变的向量基可作为 pair-force 的充分构造方式；但本阶段不冻结
任何网络或 attention 形式。对有向边独立输出两个向量、仅靠数据拟合接近反对称，不满足硬合同。

## 未来验证证据

未来同一基础状态需生成置换、统一平移、周期代表元重映射、允许旋转、pair 交换和 zero-output 六类
metamorphic cases。测试阈值与样本矩阵必须在执行前冻结。
