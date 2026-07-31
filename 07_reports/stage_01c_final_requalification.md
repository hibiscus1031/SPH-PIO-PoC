# Stage 01C 结构保持 SPH 算子最终重资格报告

日期：2026-07-31

范围：静态邻域、核一致性、制造解算子、保守压力/黏性和固定邻域原生
PyTorch 自动微分；本阶段未运行 TGV。

## 1. 最终状态

`C1_PASS_C2_PASS_C3_PASS_C4_PASS`

机器判定来自：

- `06_experiments/stage_01c_operator_candidates/results/`
  `stage01c_gate_evidence.csv`；
- `06_experiments/stage_01c_operator_candidates/results/`
  `stage01c_gate_status.txt`；
- `01_solver/structure_preserving/evaluate_requalification.py`。

该判定直接应用运行前提交的种子、支撑尺度、候选资格规则和 C1–C4
阈值，没有在查看结果后修改随机种子、\(H/dx\) 序列或通过线。

## 2. 冻结基线和执行范围

Stage 01B 基线保持在提交
`6f26750fea615c79b08a11fddfd832105b985235`，annotated tag 为
`stage-01b-v1-fail`。重资格结束时重新计算的四个冻结报告 SHA-256 为：

| 冻结文件 | SHA-256 |
|---|---|
| `07_reports/stage_01b_final_vv_report.md` | `06e8f848e1a749406fd419d92c54da784ab64c3ec87da2b183ad43f604ca4e95` |
| `07_reports/stage_01b_operator_verification.md` | `05955221bbcc787575e6813692c9f733723a77fb363a9f6e9aa505de071c06cb` |
| `07_reports/stage_01b_viscosity_parameter_audit.md` | `0a79ec1b69cfcbc5a7a6fa98b9d4b17488e818e3b5cc9cae64894864ee165729` |
| `07_reports/stage_01b_uncertainty_assessment.md` | `47d9f53e82befa8f9f995fb65290be4719b47697d8a9c9eadc88717697aafa13` |

静态统计设计在提交 `ce08c32` 预登记；固定邻域 AD 设计在提交
`1622717` 补充预登记。正式矩阵包含：

- 两条 support family；
- 5 个分辨率、3 种布局、10 个预登记种子，共 300 个 float64
  静态配置；
- 3 个代表性状态、两条 support family 和两种 dtype，共 12 个
  精度隔离配置；
- 2,496 行压力/黏性守恒记录；
- 4 个参数乘 5 个步数，共 20 行 AD–FD 记录。

最终全项目回归在警告按错误处理、禁用 pytest cache 的条件下得到
`87 passed in 8.73s`，JUnit 证据为
`06_experiments/stage_01c_operator_candidates/results/`
`pytest_regression.xml`；其中 hostname 字段已脱敏。

`per_seed_metrics.csv` 在正式 300 配置循环中记录的最大常驻内存为
947,208,192 bytes，低于预登记的 8,000,000,000 bytes 停止线。没有
修改已安装的 diffSPH 或其他第三方核心源文件。

## 3. Stage 01B 问题的因果边界

完整最小复现与证据索引见
`07_reports/stage_01c_failure_taxonomy.md`。

| ID | 现象 | 主要分类 | Stage 01C 处置 |
|---|---|---|---|
| F01 | `verletScale=1.4` 周期重复边 | upstream implementation defect | 项目侧唯一 directed-edge 集合和全拓扑审计 |
| F02 | hard-coded alpha、配置读取不可达 | upstream implementation defect | 不复用该参数传播路径；显式物理 \(\nu\) |
| F03 | generic Laplacian backward 的 `h_i=None` | upstream implementation defect | 纯原生 PyTorch value path |
| F04 | 单种子 10% jitter \(S_0\) 最高分辨率反弹 | statistical evidence limitation；固定邻居离散限制候选 | 10-seed ensemble 和两条 support 路线 |
| F05 | 单种子 10% jitter Laplacian 反弹 | statistical evidence limitation；离散限制候选 | 同上，并比较一致性修正 |
| F06 | variable-density generic viscosity 非守恒 | discretization limitation | 从对称非负 pair \(\Gamma_{ij}\) 定义作用 |
| F07 | mixed-sign Antuono pressure 非守恒 | discretization limitation | 从对称压力系数和单一径向 pair gradient 定义作用 |

因此，F01–F03 是执行栈/接口实现缺陷，不能归咎于 SPH 离散理论；
F06–F07 是原离散作用的结构限制，即使程序正常执行也不会自动获得所需
反对称性；F04–F05 的 Stage 01B 单 realization 证据足以否决那条已测试
路径，却不足以支持总体随机结论。Stage 01C 的 ensemble 结果消除了最后
一项证据不足，但没有把所有无序敏感性解释成实现 bug。

## 4. C1 — 邻域资格

`06_experiments/stage_01c_disorder_statistics/results/`
`per_seed_metrics.csv` 的 300 行均由项目侧周期 cell list 生成。每个无向
pair 只计算一次 minimum-image 几何，反向 directed edge 使用其精确负值；
这是一项 pair 几何定义，不是对最终作用做事后反对称投影。

| 检查 | 300 行最大值 | 门槛 | 结果 |
|---|---:|---:|:---:|
| duplicate edges | 0 | 0 | PASS |
| missing self edges | 0 | 0 | PASS |
| strict-support omissions | 0 | 0 | PASS |
| nonreciprocal nonself edges | 0 | 0 | PASS |
| out-of-bounds edges | 0 | 0 | PASS |
| unexpected edges | 0 | 0 | PASS |
| minimum-image Linf 差 | \(2.2204460\times10^{-16}\) | \(2.8421709\times10^{-14}\) | PASS |

`tests/test_stage01c_neighbor_deduplication.py` 还逐位检查了 float32
正反向位移、距离和 symmetric support 的互反关系。

## 5. 两条支撑尺度路线

完整表见
`06_experiments/stage_01c_support_scaling/results/support_scaling.csv`
和 `07_reports/stage_01c_support_scaling.md`。

### 5.1 Constant-neighbor family

\(H/dx=4\) 固定，物理 \(H\) 从 0.5 降到 0.125。规则布局的平均邻居数
恒为 49；5% jitter 约为 47.00，10% jitter 约为 47.54，端点比接近 1。
该路线隔离了固定邻居数细化：局部 WLS 导数仍可随网格细化下降，但 raw
\(S_0\) ensemble 不具有核一致性趋势。10% jitter raw \(S_0\) L2 均值
从 0.017983 变为 0.018265，端点比 1.0157，不能作为 C2 的一致性路线。

### 5.2 Increasing-neighbor consistency family

预登记 \(H/dx=[4,4.5,5,5.5,6]\)。尽管该比值增加，物理 \(H\) 仍从
0.5 严格降到 0.1875。平均邻居数端点为：

| 布局 | \(N=16\) | \(N=64\) | 端点比 |
|---|---:|---:|---:|
| regular | 49.000 | 113.000 | 2.3061 |
| 5% jitter | 47.0047 | 111.1225 | 2.3641 |
| 10% jitter | 47.5414 | 112.2168 | 2.3604 |

三种布局均同时满足“物理 \(H\) 严格减小”和“ensemble 平均邻居数严格
增加”。这条路线是 C2 的预登记 consistency family。

## 6. 无序统计、候选选择和制造解

每个 jitter–分辨率组合使用同一组 10 个预登记种子。结果逐 seed 保存，
并公开 mean、sample standard deviation、median、2,000 次 percentile
bootstrap 的均值 95% CI、五分辨率
\(\log(\mathrm{error})\)-\(\log(dx)\) 斜率，以及 \(N=64-N=48\) 的
paired-seed bootstrap 反弹检查。没有要求每个 seed 单独严格单调。

预登记机器选择结果保存在
`06_experiments/stage_01c_operator_candidates/results/`
`candidate_selection.csv`：

| 主要量 | 被选候选 | \(N=64\) 的 5%/10% jitter L2 几何均值 |
|---|---|---:|
| \(S_0\) | raw SPH kernel | 0.0057460 |
| gradient | quadratic weighted least squares | 0.1186692 |
| divergence | quadratic weighted least squares | 0.2122773 |
| Laplacian | quadratic weighted least squares | 0.7354497 |

Shepard 和 linear-reproducing \(S_0\) 在每个状态达到约
\(4\times10^{-16}\) 的代数归一化误差，但该机器精度地板的相对斜率和
paired rebound 不满足预登记的“严格下降”规则，因此没有被事后解释为
可排序的收敛曲线，也没有取代 raw \(S_0\) 作为 C2 主曲线。这不表示
归一化公式在物理上发散；它表示对机器零附近误差不能用相对收敛率作有利
选择。

Increasing-neighbor family 的 selected L2 ensemble 结果为：

| 布局 | 量 | \(N=16\) mean | \(N=64\) mean | 斜率 | 端点比 | 系统性 \(N=64\) 反弹 |
|---|---|---:|---:|---:|---:|:---:|
| 5% jitter | raw \(S_0\) | 0.0090050 | 0.0040638 | 0.5716 | 0.4513 | 否 |
| 10% jitter | raw \(S_0\) | 0.0179828 | 0.0081246 | 0.5708 | 0.4518 | 否 |
| 5% jitter | WLS gradient | 0.766966 | 0.118649 | 1.3504 | 0.1547 | 否 |
| 10% jitter | WLS gradient | 0.768056 | 0.118690 | 1.3511 | 0.1545 | 否 |
| 5% jitter | WLS divergence | 1.372075 | 0.212243 | 1.3504 | 0.1547 | 否 |
| 10% jitter | WLS divergence | 1.374055 | 0.212312 | 1.3512 | 0.1545 | 否 |
| 5% jitter | WLS Laplacian | 4.809762 | 0.735023 | 1.3596 | 0.1528 | 否 |
| 10% jitter | WLS Laplacian | 4.814060 | 0.735877 | 1.3594 | 0.1529 | 否 |

例如，10% jitter 的 \(N=64\) mean 95% bootstrap CI 分别为：

- raw \(S_0\)：[0.007965, 0.008276]；
- WLS gradient：[0.118686, 0.118693]；
- WLS divergence：[0.212291, 0.212331]；
- WLS Laplacian：[0.735794, 0.735961]。

四条 selected 曲线在 regular、5% jitter 和 10% jitter 上均为正斜率、
端点比小于 1，且 \(N=64-N=48\) 的 bootstrap 区间不在零以上。因此
C2 通过。

WLS、Shepard 和 reproducing corrections 仅用于插值/制造解导数候选。
最终压力和黏性 pair force 只使用未经单边矩阵修正的 symmetric radial
kernel gradient，避免以破坏 pair 结构换取制造解精度。

## 7. float32/float64 精度隔离

精度隔离先生成单一 canonical float64 布局，再转换为 float32；同一物理
配置的两个 dtype 共享
`position_reference_sha256`，因此比较没有混入另一组随机扰动。float32
结果没有被删除。

在 selected \(S_0\)/gradient/divergence/Laplacian 的代表性配置中，
float32–float64 最大绝对误差差为 \(5.52996\times10^{-6}\)，最大相对差
为 \(1.66219\times10^{-3}\)。后者来自误差本身很小的 regular
increasing-neighbor \(S_0\)；主要 WLS 导数的差异更小。相比之下，
10% jitter \(N=64\) raw \(S_0\) 约为 \(8.1\times10^{-3}\)，WLS
Laplacian 约为 0.736。

因此这些代表性状态的主误差由离散尺度和粒子无序决定，而不是 float32
累加主导；float32 仍对接近机器零的核矩和守恒残差设定可见的舍入底限。
完整双精度结果保存在
`06_experiments/stage_01c_operator_candidates/results/`
`precision_isolation.csv` 和 `precision_comparison.csv`。

## 8. C3 — 压力和黏性结构

### 8.1 对称压力

项目侧作用定义为

\[
\mathbf f^p_{ij}=-m_i m_j
\left(\frac{p_i}{\rho_i^2}+\frac{p_j}{\rho_j^2}\right)
\nabla_i W_{ij}.
\]

括号内系数交换 \(i,j\) 不变；pair-defined symmetric radial gradient
满足 \(\nabla_jW_{ji}=-\nabla_iW_{ij}\)，所以
\(\mathbf f^p_{ji}=-\mathbf f^p_{ij}\)。该作用沿 minimum-image
\(\mathbf r_{ij}\)，逐 pair 力矩为零。资格实现从实际 reverse directed
edge 独立读取梯度并重算反向公式，而不是在审计中直接写入正向作用的负值。

正压力、负压力和 mixed-sign pressure 均与 uniform/5% variable density
组合执行。所有 float64 压力/黏性行合并后的最大相对 pair 残差为
\(7.2985\times10^{-18}\)，最大相对总内力为
\(3.4059\times10^{-17}\)；float32 对应最大值为
\(2.9199\times10^{-14}\) 和 \(1.0967\times10^{-8}\)。压力逐 pair
相对力矩最大值分别为 \(3.3050\times10^{-16}\) 和
\(1.5802\times10^{-7}\)，均通过预登记 dtype 门槛。

### 8.2 对称非负黏性

预登记候选为

\[
\mathbf f^\nu_{ij}
=m_i m_j\Gamma_{ij}(\mathbf v_j-\mathbf v_i),
\]

\[
\Gamma_{ij}
=-\frac{4\nu}{\rho_i+\rho_j}
\frac{\mathbf r_{ij}\cdot\nabla_iW_{ij}}
{r_{ij}^2+(0.01H_{ij})^2}.
\]

在 \(\nu\ge0\)、正密度和径向递减 Wendland 核下，
\(\mathbf r_{ij}\cdot\nabla_iW_{ij}\le0\)，故
\(\Gamma_{ij}=\Gamma_{ji}\ge0\)。交换 pair 后速度差变号，因此作用严格
反对称。粒子功满足

\[
\sum_i\mathbf v_i\cdot\mathbf F^\nu_i
=-\sum_{i<j}m_i m_j\Gamma_{ij}
\lVert\mathbf v_j-\mathbf v_i\rVert^2\le0.
\]

最终 CSV 的 \(\Gamma_{\min}=-0.0\)；float64/float32 最大相对
\(\Gamma\) 对称残差分别为 \(2.6596\times10^{-18}\) 和
\(9.7161\times10^{-15}\)。全部黏性功为负，最大值为 -2.759583；
particle-accumulated power 与 pair-direct identity 的最大绝对差在
float64 为 \(8.8818\times10^{-16}\)，在 float32 为
\(4.7684\times10^{-7}\)。测试还确认 \(\nu=0\) 作用逐位为零，
而 \(2\nu\) 作用逐位等于两倍。

该速度差作用通常不与 \(\mathbf r_{ij}\) 平行。记录的 minimum-image
逐 pair 黏性力矩 Linf 为 \(1.1469\times10^{-5}\) 到
\(5.0095\times10^{-4}\)，因此本报告只通过线动量和耗散资格，不声称
黏性作用保证角动量。

### 8.3 制造速度和 Stage 01B 对照

在 increasing-neighbor family 中，保守 pair viscosity 的制造速度 L2
误差均值为：

| 布局 | \(N=16\) | \(N=64\) | 斜率 | 系统性最高分辨率反弹 |
|---|---:|---:|---:|:---:|
| regular | 0.068490 | 0.010656 | 1.3459 | 否 |
| 5% jitter | 0.069955 | 0.019222 | 0.9384 | 否 |
| 10% jitter | 0.074374 | 0.033723 | 0.5609 | 否 |

冻结 Stage 01B generic comparator 使用 one-sided \(m_j/\rho_j\) 权重和
\((r+10^{-8}H_i)^2\) 分母；新候选使用预登记的对称密度组合与
\(r^2+(0.01H)^2\)，所以即使 uniform density 也不是逐位相同的公式。
float64 uniform-density acceleration Linf 差为
\(4.93\times10^{-4}\) 到 \(1.568\times10^{-3}\)。在 variable density
下，Stage 01B-style comparator 的相对总内力残差为
0.025551–0.026134，而新候选仍保持上述机器精度量级的总内力。该比较说明
结构修复来自原始 pair 公式，不是把旧作用事后投影为反对称。

## 9. C4 — 原生 PyTorch 固定邻域 AD

完整报告和 20 行数据分别为：

- `07_reports/stage_01c_autograd_qualification.md`；
- `06_experiments/stage_01c_autograd/results/native_autograd_fd.csv`。

物理 \(\nu\)、初始速度幅值、一个局部速度分量和一个局部压力标量分别在
1/3/5/8/16 步上比较原生 PyTorch AD 与 centered FD。1/3/5/8 步的 16
个案例全部 finite/nonzero，最大相对差为
\(1.6190767\times10^{-5}<0.01\)。16 步的 4 个案例也全部有限、非零、
无异常，其最大诊断相对差为 \(8.9218170\times10^{-7}\)。

该路径不调用失败的 upstream custom backward。其资格范围严格限于固定
neighbor indices、固定 pair geometry、固定位置/密度/压力和速度值更新；
`topology_differentiability_claimed=False` 逐行写入 CSV。本结果不声明
邻居进入/退出、周期折返或完整求解过程的拓扑可微性。

## 10. C1–C4 判定和 V2 决策

| 门槛 | 判定 | 直接证据 |
|---|:---:|---|
| C1 邻域 | PASS | 300 行拓扑审计全部为零缺陷；minimum-image 在预登记容差内 |
| C2 统计一致性 | PASS | 四个 selected 主量在 consistency family 的三种布局均端点下降、正斜率、无系统性 \(N=64\) 反弹 |
| C3 守恒 | PASS | mixed-sign pressure、variable density、两种 dtype 的 pair/global force 和黏性功全部通过 |
| C4 自动微分 | PASS | 20/20 native AD–FD 案例 finite/nonzero；短步最大相对差低于 1% |

按照运行前停止规则，只有 C1–C4 全部通过才可重新打开 V2 fixed-physics
TGV 的设计入口。本次重资格满足该必要条件，因此 **允许重新打开 V2 的
重新设计与后续验证入口**。这不是 V2 的物理资格，也不是一次 TGV
结果；本阶段没有运行 V2 或任何 TGV。

本报告到此停止。
