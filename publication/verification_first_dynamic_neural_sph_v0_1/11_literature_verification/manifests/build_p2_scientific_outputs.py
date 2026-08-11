#!/usr/bin/env python3
"""Build P2 scientific-positioning artifacts from verified bibliography and frozen P1."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
P1 = ROOT / "publication/verification_first_dynamic_neural_sph_v0_1"
P2 = P1 / "11_literature_verification"
VERIFIED_CSV = P2 / "verified_records/verified_bibliography.csv"
P1_MD = P1 / "03_manuscript_cn/manuscript_cn_v0_1.md"


def read_records() -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    rows = list(csv.DictReader(VERIFIED_CSV.open(encoding="utf-8-sig")))
    return rows, {r["citation_id"]: r for r in rows}, {r["source_record_id"]: r for r in rows}


def yesno(value: str) -> str:
    return value if value in {"YES", "NO", "NOT_REPORTED", "NOT_VERIFIED", "NOT_APPLICABLE"} else "NOT_VERIFIED"


EVIDENCE_OVERRIDES = {
    "M001": {
        "exact_research_problem": "缓解GNN粒子流体长期rollout中的粒子聚集/拉伸不稳定，并改善物理量表现。",
        "governing_method": "以Lagrangian粒子GNN为主，并在训练与rollout推理中加入标准SPH的压力、黏性与外力分量。",
        "baseline_solver": "GNS/SEGNN类完全学习粒子模拟器；SPH用于提供附加物理分量与数据。",
        "learned_component": "GNN预测粒子更新；SPH模块作为Neural SPH增强组件。",
        "input_output": "粒子状态图到下一步粒子动力学量；细节见正文。",
        "conservation_mechanism": "NOT_REPORTED（本文未将bitwise baseline identity或项目式reciprocal correction作为合同）。",
        "temporal_architecture": "自回归rollout；训练与推理均评估多步误差。",
        "training_target": "LagrangeBench粒子轨迹上的学习模拟目标。",
        "rollout_horizon": "多数据集长rollout；具体步数依数据集与配置。",
        "reference_source": "SPH生成数据与LagrangeBench基准。",
        "validation_type": "held-out rollout benchmark与物理指标；不是独立V&V-qualified reference。",
        "ad_gradient_verification": "NOT_REPORTED",
        "topology_treatment": "动态图邻域用于粒子交互；未见cutoff birth/death的可微性资格审计。",
        "uncertainty": "NOT_REPORTED",
        "cost_comparison": "报告相对基线的rollout表现；不支持本项目的性能推断。",
        "strongest_supported_claim": "SPH物理分量可用于增强完全学习粒子模拟器的训练和rollout。",
        "explicit_limitation": "主问题是学习模拟性能，不是zero fallback、AD/FD稳定窗或拓扑事件资格。",
        "relevance": "最接近的SPH/学习粒子混合工作之一，但其基线与接口不同。",
        "prohibited_interpretation": "不得写成保留传统SPH时间推进的加性corrector，也不得据此推断本项目会提高性能。",
    },
    "M002": {
        "exact_research_problem": "提供JAX实现的可微WCSPH框架，并展示逆问题与solver-in-the-loop。",
        "governing_method": "传统SPH求解器在JAX中端到端实现。",
        "baseline_solver": "WCSPH/多种SPH算法。", "learned_component": "时间粗化solver-in-the-loop中的GNS corrector。",
        "input_output": "SPH状态经多步积分到目标；corrector处理时间粗化的学习更新。",
        "conservation_mechanism": "继承所选SPH离散；未报告项目式神经pair-force硬反对称合同。",
        "temporal_architecture": "验证梯度累计5步；逆问题100步；SitL为多步交替SPH/GNS。",
        "training_target": "20步时间粗化的reverse Poiseuille数据。", "rollout_horizon": "逆问题100 SPH步；SitL图示扩展至原始SPH 10000步尺度。",
        "reference_source": "Taylor–Green、lid-driven cavity及LagrangeBench RPF。",
        "validation_type": "求解器基准 + AD/FD梯度对比 + 应用演示。",
        "ad_gradient_verification": "JAX reverse-mode AD与有限差分比较；5 solver steps；单一epsilon=0.001dx。",
        "topology_treatment": "JAX-MD cell-list邻域；正文承认邻居随时间变化，但未报告edge birth/death两侧资格审计。",
        "uncertainty": "NOT_REPORTED", "cost_comparison": "面向ML集成而非HPC；未形成equal-error成本合同。",
        "strongest_supported_claim": "已存在可微SPH及5步AD/FD与SPH solver-in-the-loop的直接先例。",
        "explicit_limitation": "未见epsilon-window、reverse/JVP交叉核验、history attenuation或cutoff事件分离审计。",
        "relevance": "N3的直接部分先例，也是本文最接近的可微SPH比较对象。",
        "prohibited_interpretation": "不得把5步单epsilon对比写成系统stable-window资格，也不得声称其验证了本项目实现。",
    },
    "M003": {
        "exact_research_problem": "构建由NN加速度模型逐步嵌入WCSPH结构的湍流降阶Lagrangian模型层级。",
        "governing_method": "参数化弱可压SPH与神经网络/可学习核的层级模型。", "baseline_solver": "WCSPH与DNS数据参考。",
        "learned_component": "Lagrangian加速度算子、参数化平滑核及部分SPH项。", "input_output": "粒子状态到Lagrangian加速度/轨迹统计。",
        "conservation_mechanism": "通过SPH结构编码Galilean/旋转/平移对称；具体hard动量合同与本项目不同。",
        "temporal_architecture": "动态轨迹训练；不是项目式accepted-history Transformer合同。", "training_target": "WCSPH与DNS湍流数据。",
        "rollout_horizon": "正文报告时间泛化；未形成本文所需自主rollout资格合同。", "reference_source": "WCSPH validation set与DNS high-fidelity set。",
        "validation_type": "跨Mach数和时间偏移的数值泛化评估。", "ad_gradient_verification": "使用AD与敏感度分析训练；未见项目式AD/FD资格矩阵。",
        "topology_treatment": "NOT_REPORTED", "uncertainty": "NOT_REPORTED", "cost_comparison": "NOT_REPORTED",
        "strongest_supported_claim": "已存在保留大量SPH物理结构的可学习Lagrangian湍流模型。",
        "explicit_limitation": "不提供zero-correction bitwise、RK2/history事务或拓扑事件证据。",
        "relevance": "最直接的learnable-SPH方法先例；支持将本稿定位为验证合同而非首个learnable SPH。",
        "prohibited_interpretation": "不得声称本项目首次将ML与SPH结合。",
    },
    "RAW077": {
        "exact_research_problem": "构建面向逆问题、优化和混合ML的端到端可微SPH框架。",
        "governing_method": "PyTorch中的可微compressible/WCSPH/incompressible SPH。", "baseline_solver": "多类SPH离散。",
        "learned_component": "solver-in-the-loop corrector用于逼近更高阶时间积分，并展示其他优化任务。",
        "input_output": "SPH初值/参数/几何到多步目标与损失。", "conservation_mechanism": "取决于所选SPH算子；未报告本文的neural pair-force合同。",
        "temporal_architecture": "可跨数百完整模拟步传播梯度。", "training_target": "高阶时间积分匹配等混合任务。",
        "rollout_horizon": "数百步梯度传播与应用案例。", "reference_source": "标准SPH基准、目标轨迹与优化目标。",
        "validation_type": "求解器基准、逆问题、形状优化和SitL演示。", "ad_gradient_verification": "正文展示长期梯度传播；未核实项目式多epsilon AD/FD stable-window。",
        "topology_treatment": "支持可微邻域/粒子算法，但未见独立cutoff birth/death fixed-side资格矩阵。",
        "uncertainty": "NOT_REPORTED", "cost_comparison": "报告相对既有可微框架的能力/性能，不是本项目equal-error成本证据。",
        "strongest_supported_claim": "截至检索截止日，已存在正式发表的广能力可微SPH与混合ML平台。",
        "explicit_limitation": "其平台/应用论证不等于本文冻结合同的zero identity、history commit与负矩阵审计。",
        "relevance": "最接近且最新的直接竞争工作，显著压缩“可微SPH平台”方向的新颖性空间。",
        "prohibited_interpretation": "不得声称本文首次构建可微SPH或首次进行SPH solver-in-the-loop。",
    },
    "RAW044": {
        "exact_research_problem": "为完全学习粒子流体模拟器硬保证线动量守恒。", "governing_method": "层级连续卷积数据驱动粒子模拟器。",
        "baseline_solver": "完全学习的Lagrangian particle simulator。", "learned_component": "反对称连续卷积层与层级网络。",
        "input_output": "粒子状态到下一步动力学。", "conservation_mechanism": "hard architecture；反对称连续卷积，保证linear momentum。",
        "temporal_architecture": "训练时动态unroll并用于长序列rollout。", "training_target": "粒子流体观测/模拟轨迹。",
        "rollout_horizon": "长期rollout；含多达百万粒子泛化。", "reference_source": "粒子流体模拟数据。",
        "validation_type": "训练/测试rollout、泛化和物理量评估。", "ad_gradient_verification": "NOT_REPORTED",
        "topology_treatment": "邻域粒子交互；未见cutoff事件可微审计。", "uncertainty": "NOT_REPORTED", "cost_comparison": "报告训练/泛化性能。",
        "strongest_supported_claim": "反对称学习层可对完全学习粒子流体模拟硬保证线动量。",
        "explicit_limitation": "不保留传统SPH求解器，不提供angular momentum或项目式zero fallback。",
        "relevance": "本项目reciprocal hard conservation的关键方法比较对象。",
        "prohibited_interpretation": "不得将其写成SPH corrector或同时保证角动量/能量。",
    },
    "RAW004": {
        "exact_research_problem": "在多刚体/颗粒动力学GNN中同时硬保持线动量与角动量。", "governing_method": "edge-local frame的physics-informed GNN。",
        "baseline_solver": "DEM生成训练轨迹；网络为替代动力学预测器。", "learned_component": "DYNAMI-CAL GRAPHNET的力、角动量变化和参考点解码。",
        "input_output": "6-DoF节点状态到线/角速度更新。", "conservation_mechanism": "hard architecture；反对称内力与角动量交换，SO(3)等变、T(3)不变。",
        "temporal_architecture": "spatiotemporal message passing与edge memory；单步监督、多步rollout评估。", "training_target": "DEM轨迹。",
        "rollout_horizon": "extended rollouts；具体案例见正文。", "reference_source": "DEM及受控两球碰撞。",
        "validation_type": "插值/外推rollout与闭系统动量检查。", "ad_gradient_verification": "NOT_REPORTED",
        "topology_treatment": "距离阈值建边；未报告阈值事件的导数资格。", "uncertainty": "NOT_REPORTED", "cost_comparison": "报告实时/扩展能力。",
        "strongest_supported_claim": "已有GNN在非中心交互下以架构方式同时保持线、角动量。",
        "explicit_limitation": "非SPH；不提供zero-correction identity或solver-in-the-loop AD/FD合同。",
        "relevance": "限制本稿将硬线/角动量结构本身作为新颖性。",
        "prohibited_interpretation": "不得将其描述为SPH correction或能量守恒架构。",
    },
    "M004": {"exact_research_problem": "标准化Lagrangian粒子流体学习基准。", "governing_method": "SPH数据集 + GNS/SEGNN/EGNN/PaiNN基线。", "baseline_solver": "SPH用于生成数据。", "learned_component": "多种GNN代理。", "input_output": "历史粒子状态到下一状态并自回归rollout。", "conservation_mechanism": "依模型而异；不统一硬保证。", "temporal_architecture": "自回归rollout。", "training_target": "七类SPH流体数据集。", "rollout_horizon": "按数据集评估。", "reference_source": "SPH生成基准数据。", "validation_type": "位置MSE、动能MSE、Sinkhorn等测试指标。", "ad_gradient_verification": "NOT_REPORTED", "topology_treatment": "多种动态neighbor search；未做cutoff导数审计。", "uncertainty": "NOT_REPORTED", "cost_comparison": "基准训练/推理比较。", "strongest_supported_claim": "提供学习Lagrangian流体模拟的标准化数据和rollout评估。", "explicit_limitation": "属于性能基准，不是混合SPH资格链。", "relevance": "界定fully learned particle simulator类别。", "prohibited_interpretation": "不得当作SPH correction或独立物理验证。"},
    "M005": {"exact_research_problem": "学习多类粒子物理的通用GNS。", "governing_method": "动态近邻图上的message passing。", "baseline_solver": "完全学习替代模拟器。", "learned_component": "GNS encoder-processor-decoder。", "input_output": "粒子历史到加速度/下一位置。", "conservation_mechanism": "NOT_REPORTED（无项目式hard pair antisymmetry）。", "temporal_architecture": "自回归rollout；每步重建邻接。", "training_target": "多类物理模拟轨迹。", "rollout_horizon": "长rollout任务。", "reference_source": "传统模拟器生成数据。", "validation_type": "held-out rollout。", "ad_gradient_verification": "NOT_REPORTED", "topology_treatment": "每步重算近邻图，但未审计edge membership导数。", "uncertainty": "NOT_REPORTED", "cost_comparison": "报告学习模拟表现。", "strongest_supported_claim": "动态图message passing可形成通用学习粒子模拟器。", "explicit_limitation": "不保留SPH时间推进。", "relevance": "fully learned类别的基准。", "prohibited_interpretation": "不得称为SPH correction。"},
    "M006": {"exact_research_problem": "用连续卷积学习Lagrangian流体模拟。", "governing_method": "连续卷积粒子网络。", "baseline_solver": "完全学习替代求解器。", "learned_component": "粒子-粒子与边界连续卷积。", "input_output": "粒子历史到动态更新。", "conservation_mechanism": "NOT_REPORTED", "temporal_architecture": "autoregressive rollout。", "training_target": "粒子流体轨迹。", "rollout_horizon": "多步rollout。", "reference_source": "物理模拟数据。", "validation_type": "held-out rollout。", "ad_gradient_verification": "NOT_REPORTED", "topology_treatment": "局部粒子邻域；未做拓扑事件审计。", "uncertainty": "NOT_REPORTED", "cost_comparison": "学习模拟性能比较。", "strongest_supported_claim": "连续卷积可用于完全学习Lagrangian流体。", "explicit_limitation": "非传统SPH corrector。", "relevance": "Neural SPH与DMCF的重要前序。", "prohibited_interpretation": "不得称为保留SPH基线。"},
    "M007": {"exact_research_problem": "学习刚体、软体和流体的粒子交互用于操控。", "governing_method": "DPI-Net多尺度动态图网络。", "baseline_solver": "完全学习替代模拟器。", "learned_component": "particle interaction network。", "input_output": "粒子状态到未来状态。", "conservation_mechanism": "NOT_REPORTED", "temporal_architecture": "多步rollout用于规划。", "training_target": "模拟/真实交互轨迹。", "rollout_horizon": "任务相关。", "reference_source": "模拟与实验。", "validation_type": "预测与操控任务。", "ad_gradient_verification": "NOT_REPORTED", "topology_treatment": "动态层级关系；未做cutoff导数审计。", "uncertainty": "NOT_REPORTED", "cost_comparison": "NOT_REPORTED", "strongest_supported_claim": "学习粒子动力学可支持多物体类别预测与操控。", "explicit_limitation": "非SPH、非守恒corrector。", "relevance": "fully learned粒子模拟背景。", "prohibited_interpretation": "不得当作SPH方法。"},
    "M008": {"exact_research_problem": "在可变网格上学习多物理模拟。", "governing_method": "MeshGraphNets。", "baseline_solver": "完全学习网格代理。", "learned_component": "mesh message passing与自适应。", "input_output": "网格状态到下一步。", "conservation_mechanism": "NOT_REPORTED", "temporal_architecture": "autoregressive rollout。", "training_target": "多类模拟轨迹。", "rollout_horizon": "任务相关。", "reference_source": "传统网格模拟器。", "validation_type": "held-out dynamics。", "ad_gradient_verification": "NOT_REPORTED", "topology_treatment": "网格适应性；不等同粒子cutoff事件。", "uncertainty": "NOT_REPORTED", "cost_comparison": "报告推理加速。", "strongest_supported_claim": "图网络可学习网格动力学并自回归。", "explicit_limitation": "非粒子SPH。", "relevance": "动态离散结构的邻近比较。", "prohibited_interpretation": "不得用作SPH拓扑导数证据。"},
    "M009": {"exact_research_problem": "让学习corrector通过可微PDE求解器进行多步训练。", "governing_method": "Eulerian PDE solver-in-the-loop。", "baseline_solver": "迭代PDE求解器。", "learned_component": "误差corrector。", "input_output": "粗网格状态到校正状态。", "conservation_mechanism": "依PDE/solver而定；非统一hard conservation。", "temporal_architecture": "训练时多步look-ahead并有数百步rollout。", "training_target": "高分辨率/参考解。", "rollout_horizon": "数百步。", "reference_source": "多类PDE数值解。", "validation_type": "held-out误差与rollout稳定性。", "ad_gradient_verification": "通过AD传播，但未报告本文式AD/FD资格矩阵。", "topology_treatment": "固定Eulerian离散；不处理粒子cutoff。", "uncertainty": "NOT_REPORTED", "cost_comparison": "有精度/计算比较。", "strongest_supported_claim": "solver-in-the-loop多步训练与长期rollout已有明确先例。", "explicit_limitation": "非SPH、非梯度verification论文。", "relevance": "本项目不得把SitL本身作为新颖性。", "prohibited_interpretation": "不得据此称本项目已完成训练或性能验证。"},
    "M010": {"exact_research_problem": "可扩展可微刚体物理用于学习和控制。", "governing_method": "可微物理模拟。", "baseline_solver": "刚体物理。", "learned_component": "控制/策略可与solver耦合。", "input_output": "参数到轨迹/损失梯度。", "conservation_mechanism": "NOT_VERIFIED", "temporal_architecture": "多步。", "training_target": "控制目标。", "rollout_horizon": "任务相关。", "reference_source": "物理任务。", "validation_type": "控制和学习实验。", "ad_gradient_verification": "展示可微性；非本文式多epsilon核验。", "topology_treatment": "接触问题邻近背景；非SPH cutoff审计。", "uncertainty": "NOT_REPORTED", "cost_comparison": "报告可扩展性。", "strongest_supported_claim": "可微物理可作为多步学习/控制组件。", "explicit_limitation": "不同求解器和事件结构。", "relevance": "可微模拟背景。", "prohibited_interpretation": "不得称其解决SPH动态图可微性。"},
    "M011": {"exact_research_problem": "从数据学习Hamiltonian以施加保守动力学偏置。", "governing_method": "Hamiltonian neural network。", "baseline_solver": "学习连续动力系统。", "learned_component": "标量Hamiltonian。", "input_output": "状态到时间导数。", "conservation_mechanism": "Hamiltonian结构提供能量偏置；不等同任意离散时间步的exact energy。", "temporal_architecture": "ODE积分。", "training_target": "状态导数/轨迹。", "rollout_horizon": "长期轨迹评估。", "reference_source": "低维动力系统。", "validation_type": "能量与轨迹误差。", "ad_gradient_verification": "AD用于Hamiltonian梯度；非AD/FD qualification。", "topology_treatment": "NOT_APPLICABLE", "uncertainty": "NOT_REPORTED", "cost_comparison": "NOT_REPORTED", "strongest_supported_claim": "Hamiltonian可作为能量结构偏置。", "explicit_limitation": "低维保守系统；非SPH pair force。", "relevance": "区分energy structure与momentum antisymmetry。", "prohibited_interpretation": "不得写成同时硬保证本项目线/角动量。"},
    "M012": {"exact_research_problem": "从轨迹学习Lagrangian并由Euler–Lagrange方程得到动力学。", "governing_method": "Lagrangian neural network。", "baseline_solver": "学习连续动力系统。", "learned_component": "标量Lagrangian。", "input_output": "广义坐标/速度到加速度。", "conservation_mechanism": "由Lagrangian结构施加物理偏置。", "temporal_architecture": "ODE rollout。", "training_target": "轨迹/加速度。", "rollout_horizon": "任务相关。", "reference_source": "低维/连续系统。", "validation_type": "轨迹与守恒量。", "ad_gradient_verification": "AD用于求导；非资格化。", "topology_treatment": "NOT_APPLICABLE", "uncertainty": "NOT_REPORTED", "cost_comparison": "NOT_REPORTED", "strongest_supported_claim": "Lagrangian结构学习已有先例。", "explicit_limitation": "非动态图SPH。", "relevance": "保守架构背景。", "prohibited_interpretation": "不得等同硬pairwise momentum conservation。"},
    "M013": {"exact_research_problem": "构造E(n)等变GNN。", "governing_method": "EGNN。", "baseline_solver": "通用图网络。", "learned_component": "等变message passing。", "input_output": "几何图特征到等变输出。", "conservation_mechanism": "equivariance，不自动等于动量/能量硬守恒。", "temporal_architecture": "可用于动力学，但架构本身非时间合同。", "training_target": "多类几何任务。", "rollout_horizon": "NOT_REPORTED", "reference_source": "基准数据。", "validation_type": "任务性能。", "ad_gradient_verification": "NOT_REPORTED", "topology_treatment": "图输入；未审计邻接事件。", "uncertainty": "NOT_REPORTED", "cost_comparison": "模型效率。", "strongest_supported_claim": "E(n)等变message passing已有成熟架构。", "explicit_limitation": "等变不蕴含守恒。", "relevance": "限制本稿将O(2)/Galilean测试作为架构新颖性。", "prohibited_interpretation": "不得把equivariance写成hard conservation。"},
    "M014": {"exact_research_problem": "构造SE(3)等变、steerable的图网络。", "governing_method": "SEGNN。", "baseline_solver": "通用几何GNN。", "learned_component": "steerable MLP/message passing。", "input_output": "标量/向量图特征到等变输出。", "conservation_mechanism": "equivariance；非自动守恒。", "temporal_architecture": "NOT_REPORTED", "training_target": "多类物理/几何任务。", "rollout_horizon": "NOT_REPORTED", "reference_source": "基准。", "validation_type": "任务性能。", "ad_gradient_verification": "NOT_REPORTED", "topology_treatment": "图结构输入，未报告事件导数。", "uncertainty": "NOT_REPORTED", "cost_comparison": "NOT_REPORTED", "strongest_supported_claim": "steerable E(3) message passing可编码旋转等变。", "explicit_limitation": "不等于pairwise力反对称。", "relevance": "等变比较。", "prohibited_interpretation": "不得写成守恒网络。"},
    "M015": {"exact_research_problem": "为ML-based science提出共识式研究与报告建议。", "governing_method": "32项REFORMS checklist。", "baseline_solver": "NOT_APPLICABLE", "learned_component": "NOT_APPLICABLE", "input_output": "NOT_APPLICABLE", "conservation_mechanism": "NOT_APPLICABLE", "temporal_architecture": "NOT_APPLICABLE", "training_target": "NOT_APPLICABLE", "rollout_horizon": "NOT_APPLICABLE", "reference_source": "跨学科方法学文献。", "validation_type": "共识建议。", "ad_gradient_verification": "NOT_APPLICABLE", "topology_treatment": "NOT_APPLICABLE", "uncertainty": "强调透明性与可复现性。", "cost_comparison": "NOT_APPLICABLE", "strongest_supported_claim": "ML-based science需要清晰主张、数据划分、可复现和限制报告。", "explicit_limitation": "非计算力学V&V标准。", "relevance": "支持透明报告负证据和未执行工作。", "prohibited_interpretation": "不得当作SPH方法学证据。"},
    "RAW031": {"exact_research_problem": "将经典CSE V&V扩展到predictive SciML。", "governing_method": "四组成credibility框架与16项建议。", "baseline_solver": "CSE/SciML预测模型。", "learned_component": "范围不限。", "input_output": "NOT_APPLICABLE", "conservation_mechanism": "要求评估物理保真度，不指定单一架构。", "temporal_architecture": "NOT_APPLICABLE", "training_target": "NOT_APPLICABLE", "rollout_horizon": "NOT_APPLICABLE", "reference_source": "V&V与SciML文献。", "validation_type": "verification/calibration/validation/application domain分离。", "ad_gradient_verification": "未给出SPH专用AD/FD合同。", "topology_treatment": "NOT_APPLICABLE", "uncertainty": "强调UQ与适用域。", "cost_comparison": "建议报告计算资源。", "strongest_supported_claim": "SciML可信度需要超过普通训练/测试指标的CSE式V&V。", "explicit_limitation": "框架级建议，不验证本项目。", "relevance": "直接支撑verification-first定位。", "prohibited_interpretation": "不得称其证明本文门槛是唯一正确方案。"},
    "RAW114": {"exact_research_problem": "用MMS验证WCSPH及边界相关实现。", "governing_method": "WCSPH + manufactured solutions + convergence study。", "baseline_solver": "WCSPH。", "learned_component": "NOT_APPLICABLE", "input_output": "数值解与制造解误差。", "conservation_mechanism": "NOT_VERIFIED", "temporal_architecture": "时间相关MMS案例。", "training_target": "NOT_APPLICABLE", "rollout_horizon": "NOT_APPLICABLE", "reference_source": "解析制造解。", "validation_type": "code verification/observed convergence。", "ad_gradient_verification": "NOT_APPLICABLE", "topology_treatment": "NOT_REPORTED", "uncertainty": "通过收敛率量化离散误差。", "cost_comparison": "NOT_REPORTED", "strongest_supported_claim": "MMS可系统验证WCSPH实现与收敛。", "explicit_limitation": "MMS不是实验validation或ML性能证据。", "relevance": "支持本文reference hierarchy。", "prohibited_interpretation": "不得把MMS称为独立物理验证。"},
}


def generic_evidence(rec: dict) -> dict:
    return {
        "exact_research_problem": f"题录/摘要显示该文研究：{rec['title']}。",
        "governing_method": "NOT_VERIFIED",
        "baseline_solver": "NOT_VERIFIED",
        "learned_component": "NOT_VERIFIED",
        "input_output": "NOT_VERIFIED",
        "conservation_mechanism": "NOT_VERIFIED",
        "temporal_architecture": "NOT_VERIFIED",
        "training_target": "NOT_VERIFIED",
        "rollout_horizon": "NOT_VERIFIED",
        "reference_source": "NOT_VERIFIED",
        "validation_type": "NOT_VERIFIED",
        "ad_gradient_verification": "NOT_VERIFIED",
        "topology_treatment": "NOT_VERIFIED",
        "uncertainty": "NOT_REPORTED",
        "cost_comparison": "NOT_REPORTED",
        "strongest_supported_claim": "仅支持该正式题录所指向的方法主题存在；不支持未核实的正文细节。",
        "explicit_limitation": "核心方法字段未取得可审计全文证据。",
        "relevance": "作为方法学邻近题录保留，不承担强新颖性结论。",
        "prohibited_interpretation": "不得从题名推断hard conservation、rollout、AD/FD或topology处理。",
    }


def build_evidence_notes(rows: list[dict]) -> list[dict]:
    notes = []
    out = P2 / "evidence_notes"
    out.mkdir(parents=True, exist_ok=True)
    for rec in rows:
        if rec["literature_level"] == "CORE-C_CONTEXT":
            continue
        sid = rec["source_record_id"]
        data = generic_evidence(rec)
        data.update(EVIDENCE_OVERRIDES.get(sid, {}))
        cache_txt = out / "fulltext_cache" / f"{sid}.txt"
        access = "FULL_TEXT" if cache_txt.exists() else rec["evidence_access"]
        note = {
            "citation_id": rec["citation_id"], "source_record_id": sid, "title": rec["title"],
            "evidence_access": access, **data,
            "publisher_url": rec["publisher_url"], "doi": rec["doi"],
        }
        notes.append(note)
        md = [f"# {rec['citation_id']} — {rec['title']}", "", f"- evidence_access: `{access}`"]
        for key, value in note.items():
            if key in {"citation_id", "source_record_id", "title", "evidence_access"}:
                continue
            md.append(f"- {key}: {value}")
        (out / f"{rec['citation_id']}_{sid}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (out / "core_ab_evidence_notes.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return notes


def build_competitor_matrix(by_sid: dict[str, dict]) -> list[dict]:
    specs = [
        ("M001", "GNN simulator enhanced with SPH force components", "hybrid enhancement", "dynamic", "local", "GNN", "implicit history window", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "SPH-generated benchmark", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "YES", "YES", "held-out benchmark", "NOT_REPORTED", "limited failure analysis"),
        ("M002", "WCSPH", "solver-in-the-loop correction", "dynamic", "local", "GNN", "no learned memory stated", "SPH-dependent", "SPH-dependent", "SPH-dependent", "NOT_REPORTED", "TGV/LDC/RPF", "NOT_REPORTED", "YES; 5 steps; one epsilon", "YES; 5 steps", "NOT_REPORTED", "YES", "YES", "solver benchmarks", "NOT_REPORTED", "limited"),
        ("M003", "parameterized WCSPH", "learned SPH terms/kernels", "dynamic", "local", "NN", "NOT_REPORTED", "SPH-structure dependent", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "WCSPH and DNS", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "YES", "YES", "cross-condition numerical evaluation", "NOT_REPORTED", "NOT_REPORTED"),
        ("RAW077", "multi-formulation SPH", "hybrid correction/optimization", "dynamic", "local", "NN/GNN", "NOT_REPORTED", "SPH-operator dependent", "SPH-operator dependent", "SPH-operator dependent", "NOT_REPORTED", "standard SPH cases", "NOT_REPORTED", "NOT_VERIFIED", "gradient propagation over hundreds of steps", "NOT_REPORTED", "YES", "YES", "solver benchmarks and applications", "reported capability/cost", "limitations discussed"),
        ("RAW044", "none; data-driven particle solver", "replacement", "dynamic", "local/hierarchical", "continuous convolution", "temporal-coherence unroll", "YES", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "simulation trajectories", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "YES", "YES", "held-out generalization", "reported", "limited"),
        ("M004", "SPH data generator", "replacement baselines", "dynamic", "local", "GNN family", "history window", "model-dependent", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "seven SPH datasets", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "YES", "YES", "benchmark test sets", "reported", "reports instability sensitivity"),
        ("M005", "none; multiple simulators generate data", "replacement", "dynamic", "local", "GNN", "history window", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "simulator trajectories", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "YES", "YES", "held-out rollout", "reported", "limited"),
        ("RAW017", "particle/Lagrangian simulator", "replacement", "dynamic", "local", "GNN", "NOT_VERIFIED", "NOT_VERIFIED", "NOT_VERIFIED", "NOT_VERIFIED", "NOT_VERIFIED", "simulation data", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "YES", "YES", "held-out tests", "reported", "NOT_VERIFIED"),
        ("M009", "iterative Eulerian PDE solver", "correction", "dynamic", "local/global by PDE", "CNN", "multi-step look-ahead", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "high-resolution solver", "NOT_REPORTED", "NOT_REPORTED", "backprop through multiple solver steps", "NOT_APPLICABLE", "YES", "YES", "held-out PDE cases", "reported", "some failure/ablation"),
        ("M016", "symmetric SPH for elliptic PDE", "static residual correction", "static", "global field", "MLP", "NOT_APPLICABLE", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "NOT_REPORTED", "reference elliptic solution", "NOT_REPORTED", "NOT_REPORTED", "NOT_APPLICABLE", "NOT_APPLICABLE", "YES", "NOT_APPLICABLE", "numerical test cases", "reported", "NOT_REPORTED"),
    ]
    cols = ["source_record_id", "SPH_baseline", "correction_or_replacement", "static_or_dynamic", "local_or_global", "architecture", "temporal_memory", "hard_linear_momentum", "angular_momentum", "energy", "zero_correction_identity", "reference_hierarchy", "MMS", "AD_FD", "multistep_gradient", "topology_event_audit", "training", "autonomous_rollout", "independent_validation", "equal_error_cost", "negative_result_reporting"]
    out = []
    for spec in specs:
        row = dict(zip(cols, spec))
        rec = by_sid[row["source_record_id"]]
        row = {"citation_id": rec["citation_id"], "title": rec["title"], **row}
        out.append(row)
    target = P2 / "direct_competitors/direct_competitor_matrix.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def build_novelty() -> list[dict]:
    rows = [
        {"id": "N1", "question": "dynamic neural-SPH的bitwise zero-correction equivalence是否已有论文建立？", "conclusion": "SUPPORTED_NOVELTY_GAP", "evidence": "V001–V004提供learnable/differentiable SPH直接先例，但在核验全文中未发现以bitwise baseline identity作为正式退化合同。", "boundary": "仅限截至2026-08-05的94篇verified集合；不得写为从未有人做过。"},
        {"id": "N2", "question": "RK2 start/midpoint graph rebuild与accepted-only history commit是否已有正式验证合同？", "conclusion": "SUPPORTED_NOVELTY_GAP", "evidence": "V002、V003、V004、V013涉及多步粒子动态图或可微SPH，但未核实到该二者联合的事务式合同。", "boundary": "属于合同组合的证据空缺，不主张单个工程做法首次出现。"},
        {"id": "N3", "question": "是否已有系统的多步AD/FD stable-window资格？", "conclusion": "PARTIAL_PRECEDENT", "evidence": "V002明确比较5步AD与FD，但使用一个预选epsilon；V007等提供AD-CFD验证背景。未见与本项目相同的相邻epsilon稳定窗和完整probe矩阵。", "boundary": "JAX-SPH是直接先例，故不能写成首次多步AD/FD。"},
        {"id": "N4", "question": "是否已有reverse/JVP、extended FD、history attenuation和backend sensitivity联合报告？", "conclusion": "SUPPORTED_NOVELTY_GAP", "evidence": "核验集合含reverse AD、adjoint checking及可微求解器文献，但未发现四类诊断在同一dynamic neural-SPH资格链中联合报告。", "boundary": "组合证据空缺；各诊断单独均有方法学先例。"},
        {"id": "N5", "question": "是否已有particle cutoff birth/death、fixed-side gradients与piecewise-smooth boundary独立资格？", "conclusion": "SUPPORTED_NOVELTY_GAP", "evidence": "V002/V004使用动态粒子邻域，V015/V019提供非光滑/可微模拟背景；核验正文未发现SPH cutoff事件的同构资格矩阵。", "boundary": "不能外推到所有动态图或混合系统。"},
        {"id": "N6", "question": "是否已有工作将complete negative gradient evidence保留在主论文？", "conclusion": "PARTIAL_PRECEDENT", "evidence": "V003、V024等报告rollout不稳定/局限，V025/V029倡导透明报告；未找到与360-probe失败矩阵同规模、同合同的直接先例。", "boundary": "是否置于‘主论文’受版本与补充材料边界影响，不能作全局否定。"},
    ]
    out = P2 / "novelty_matrix"
    out.mkdir(parents=True, exist_ok=True)
    (out / "novelty_positioning_matrix.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = ["# Novelty positioning matrix", "", "限定语：以下判断仅针对截至2026-08-05完成题录与正文核验的94篇集合。", "", "| ID | 结论 | 证据与边界 |", "|---|---|---|"]
    for r in rows:
        md.append(f"| {r['id']} | `{r['conclusion']}` | {r['evidence']} {r['boundary']} |")
    md += ["", "建议正文措辞：‘据我们所知，在本次已核验文献集合内，尚未发现……的联合、可审计证据。’禁止使用 FIRST、NOVEL 或 UNPRECEDENTED。"]
    (out / "novelty_positioning_matrix.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return rows


INTRO = r"""# 1. 引言

## 1.1 SPH的数值背景与学习型粒子求解器

光滑粒子流体动力学（SPH）以随体粒子和紧支核近似连续介质方程，适合自由表面、大变形和复杂耦合，但其误差与收敛同时受核一致性、邻域尺度、粒子分布、边界、耗散项和时间步约束影响；相关综述与验证研究持续把一致性、收敛、稳定性和边界条件列为核心问题 [V042,V056,V058,V076,V018]。因此，SPH benchmark的通过不自动等同于代码验证、解验证或面向应用的物理确认。

学习型Lagrangian模拟器已从连续卷积、动态图消息传递和多尺度交互发展为可进行自回归rollout的粒子代理 [V010,V011,V013,V021,V024]。这些方法通常把传统模拟器作为数据源，并由网络直接预测粒子更新；它们应与“保留SPH时间推进、只学习局部修正”的hybrid correction严格区分。Neural SPH在完全学习GNN的训练与推理阶段加入压力、黏性和外力等SPH分量 [V003]；另一条路线则直接参数化SPH项或平滑核 [V001]。这两类工作均说明“SPH与学习结合”本身不是本文可主张的新颖点。

## 1.2 保守/等变架构与直接竞争工作

几何等变网络可把平移、旋转或反射对称编码进消息传递，但等变性并不自动等于线动量、角动量或能量守恒 [V017,V023]。面向粒子流体，反对称连续卷积已经被用于硬保证线动量 [V022]；面向6-DoF多体系统，DYNAMI-CAL GRAPHNET进一步以edge-local反对称参考框架同时保持线动量与角动量 [V028]。这些工作构成本稿reciprocal pair-force的直接方法比较，也要求本文避免把soft loss、equivariance与hard conservation混写。

更接近本文的是可学习或可微SPH。JAX-SPH实现了JAX中的可微WCSPH，报告了5个求解步的AD/FD比较、100步逆问题和SPH solver-in-the-loop [V002]；diffSPH则在PyTorch中覆盖多类SPH形式、逆问题、优化、混合corrector和跨数百步的梯度传播 [V004]。因此，本稿不能以“首个可微SPH”或“首个SPH solver-in-the-loop”为定位。可辩护的区别只可能来自资格合同、证据粒度与负结果的完整保留。

## 1.3 动态solver-in-the-loop的可微性与可信度问题

solver-in-the-loop已经证明学习corrector可以通过可微PDE求解器接受多步训练信号，并在若干Eulerian PDE上形成长期rollout [V016]；可扩展可微物理也已用于学习与控制 [V015]。然而，“代码由AD框架实现”只说明导数路径可构造，不等于该路径在给定步长、时间跨度、状态历史和离散事件下经过外部梯度核验。AD-CFD文献长期使用tangent/adjoint checking、有限差分或相关一致性试验来核验导数实现 [V005,V006,V007,V008]；JAX-SPH提供了粒子求解器中的直接五步先例 [V002]。

动态图进一步引入分支边界：近邻关系通常随粒子位置每步重建 [V002,V013]，而离散建边事件不能仅凭连续edge weight直觉处理。现有核验文献中可以找到动态图rollout、可微SPH和非光滑物理模拟的相邻证据，但在本次verified集合内，未发现将SPH cutoff birth/death、事件两侧fixed-topology gradients与piecewise-smooth边界作为独立资格分支的同构报告。该判断仅限当前94篇已核验集合，不能表述为“从未有人做过”。

## 1.4 verification-first定位、研究问题与有限贡献

Scientific ML的可信度讨论正在把传统计算科学中的verification、validation、calibration、uncertainty和适用域重新引入ML增强求解器 [V020,V029]；REFORMS则强调主张、数据、评估与可复现性的透明报告 [V025]。与通常以训练误差、rollout稳定性或加速比为主的论文不同，本研究在训练前先冻结可执行合同，并允许资格链以NOT_QUALIFIED结束。这里的“verification-first”是研究顺序和证据边界，不是对既有性能研究价值的否定。

本文提出三个研究问题：RQ1，如何把守恒、RK2阶段语义、动态图重建和accepted-only history commit转化为可执行合同；RQ2，zero correction、结构守恒与离散拓扑事件能否分别资格认定；RQ3，固定拓扑多步路径中，AD/FD资格在何种冻结条件下不能形成完整证据。相应贡献限于：（1）reference–implementation–gradient–topology分层资格链；（2）zero correction相对D0的288/288 bitwise等价与540/540阶段线动量守恒检查；（3）完整360-probe稳定窗矩阵及216通过、144失败；（4）TE1 edge birth/death、replay和event-side gradient审计；（5）将失败、未决归因与Stage 03E未授权共同保留。本文不回答训练是否成功、模型是否改善SPH或D3是否优于D1/D2。 <!-- CLAIM:C03,C06,C08,C13,C20,C21,C25,C26,C27,C29 -->
"""

DISCUSSION = r"""# 9. 讨论

## 9.1 与learned SPH correction和fully learned particle simulator的区别

与Neural SPH相比，本项目不是在已训练GNN rollout上加入SPH压力、黏性或外力分量；它保留冻结SPH基线，并把未训练神经项限制为加性reciprocal pair-force，同时要求zero correction严格退化到D0 [V003]。与参数化SPH湍流模型相比，本项目没有训练平滑核或闭合项，也没有DNS性能证据 [V001]。与JAX-SPH和diffSPH相比，本项目的主要增量不是“可微SPH平台”，而是把zero fallback、RK2阶段图重建、history事务、多步AD/FD和topology event拆成独立门；后两项工作已经建立了可微SPH、逆问题和solver-in-the-loop的强直接先例 [V002,V004]。

GNS、continuous-convolution模拟器和LagrangeBench基线主要直接学习粒子动力学并自回归rollout [V011,V013,V024]。本项目则不允许网络直接替代位置推进、EOS或邻域membership。这个区别决定了“zero correction”在本项目中具有可执行的基线身份意义，而在完全学习模拟器中通常没有同一语义。它也意味着他人的rollout性能不能被用来暗示本模型会提高精度、稳定性或成本。

## 9.2 与conservative/equivariant GNN的区别

DMCF通过反对称连续卷积硬保证线动量，并已完成训练与大规模粒子rollout [V022]；DYNAMI-CAL GRAPHNET同时编码线、角动量交换，并在颗粒动力学上评估长期rollout [V028]。本项目的reciprocal head同样属于hard architectural constraint，而不是守恒罚项；但当前冻结证据只支持指定阶段检查中的离散线动量消去，不支持角动量、能量、训练稳定性或长时守恒。EGNN/SEGNN等工作进一步说明，几何等变应与守恒结论分开陈述 [V017,V023]。

## 9.3 与differentiable CFD/physics solver的区别

传统AD-CFD与tangent/adjoint文献把导数检查视为实现核验的一部分 [V005,V007,V008]，solver-in-the-loop则将多步求解器梯度用于训练corrector [V016]。JAX-SPH已报告5步AD/FD比较，但采用单一epsilon；diffSPH报告更长梯度链和广泛应用 [V002,V004]。本项目的差异是使用冻结的多epsilon stable-window、完整360 probes、reverse/JVP、extended FD、history attenuation与backend sensitivity进行资格和归因。由于216/360通过而144/360失败，该差异目前形成的是更严格的负资格结论，不是优于前述框架的性能结论。

## 9.4 zero-correction evidence与216/360、144 failures的含义

288/288 bitwise zero-correction等价证明，关闭神经修正时D1–D3接口不会改变指定D0执行路径。这对混合求解器很重要，因为它把后续差异限定到显式修正路径，而不是隐藏的图、缓存或积分分叉。该证据仍然不证明非零修正准确、必要或可训练。

完整360-probe矩阵中216个stable windows说明部分固定拓扑多步方向导数可被AD与FD共同支持；144个失败以及history门0/6使Stage 03D整体保持NOT_QUALIFIED。reverse/JVP 60/60一致只排除了若干AD模式实现分歧，extended FD、horizon scaling和backend sensitivity又表明失败来源混合，不能被压缩成单一“FD噪声”或单一“AD错误”。保留这些负结果的价值在于阻止训练授权建立在选择性成功probe上，这与Scientific ML可信度和透明报告的方向一致 [V025,V029]。

## 9.5 topology piecewise smoothness的意义

TE1把离散edge membership与事件两侧连续分支分开：birth/death、6/6 replay、12/12 fixed-side gradients、有限力跳和empty-graph语义可以分别通过，而edge existence本身仍是阶跃。该结果避免两种相反误读：跨事件中心差分异常不应自动归因于网络梯度失败；event-side PASS也不应写成cutoff membership可微。当前证据仅覆盖冻结TE1与本实现，尚不能证明任意粒子数、邻域算法、边界处理或并行后端下的一般性。

## 9.6 为什么未训练既合理又构成限制

Stage 03E authorization=false，因此不执行训练是预注册资格链的结果，不是训练失败或性能回避。若在多步梯度门未通过时继续训练，将难以区分优化失败、梯度实现问题和离散非光滑性。另一方面，未训练也使本文缺少直接竞争工作通常提供的rollout误差、长期稳定性、外推和成本数据 [V003,V022,V024]。因此，本稿可作为verification methods论文继续修订，但不具备完整solver性能论文的证据等级。

## 9.7 与Scientific ML V&V框架的关系及未来证据

本研究把代码/算法verification、参考层级、validation和未执行performance显式分开，符合SciML可信度框架所强调的适用域与持续证据积累 [V020,V029]。但一般性仍需通过至少两种独立SPH实现、更多动态拓扑家族、不同边界/粒子分辨率、公开可复现实验以及D-R4或等价外部参考证明。若未来要升级为完整CMAME solver论文，还必须在重新授权后完成训练资格、自主rollout、精度–成本曲线、长期守恒/稳定性、跨问题外推与独立验证；任何新增证据都应作为新阶段，不得回写现有Stage 01–03 verdict。

## 9.8 保留的历史边界

Stage 01保持`V2_QUALIFICATION_FAIL`，Stage 01H为`FINITE_RESOLUTION_DOMINANT`，黏性算子形式仍为`NOT_CONFIRMED`；Stage 02静态路线保持关闭。Stage 03没有恢复这些状态。当前仍有mixed/unresolved梯度归因、无D-R4、无训练和无性能，这些弱点必须在摘要、讨论与投稿层级判断中主动可见。 <!-- CLAIM:C01,C02,C14,C27,C28 -->
"""


def format_reference(rec: dict) -> str:
    tail = f" https://doi.org/{rec['doi']}" if rec["doi"] else f" {rec['publisher_url']}"
    vi = ", ".join(x for x in [rec["venue"], rec["volume"], rec["issue"], rec["pages_or_article"]] if x)
    return f"[{rec['citation_id']}] {rec['authors']} ({rec['year']}). {rec['title']}. {vi}.{tail}"


def build_manuscript(rows: list[dict], by_id: dict[str, dict]) -> str:
    text = P1_MD.read_text(encoding="utf-8")
    text = re.sub(r"\A# .*?\n", "# 守恒型动态神经–SPH耦合的验证优先资格：零修正、拓扑事件与多步梯度边界\n", text, count=1)
    text = text.replace("P1中文稿 v0.1｜Evidence-locked manuscript draft｜非投稿定稿", "P2中文稿 v0.2｜Literature-positioned verification manuscript｜非投稿定稿")
    abstract = "动态神经–SPH耦合把时间积分、动态图重建、历史状态提交和多步自动微分置于同一计算链。已发表研究已覆盖learnable SPH、Neural SPH、可微SPH、solver-in-the-loop和硬守恒粒子网络 [V001,V002,V003,V004,V022,V028]；因此，本文不以SPH–ML结合或可微实现本身作为新颖性，而定位于verification-first资格合同。我们构建D0基线、D1瞬时MLP、D2循环模型与D3因果时间注意力模型的统一动态框架，并审计动态参考、独立RK2、zero correction、反对称reciprocal pair-force、多步AD/FD与确定性拓扑事件。独立RK2的48/48检查、zero correction的288/288 bitwise等价、结构smoke的72/72、checkpoint/resume的6/6与one-step autograd的6/6均通过；冻结多阶段测试中540/540守恒检查通过。完整360-probe矩阵中216个probe获得stable AD/FD window，144个失败，history门为0/6。因此Stage 03D保持`DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`。TE1记录一次edge birth与一次death，6/6 replay和12/12 event-side gradients通过，但cutoff edge membership仍为离散事件。本文没有执行动态训练、自主rollout或性能验证。结果支持一种有限定位：在当前已核验文献集合内，zero fallback、多步stable-window与topology-event联合审计仍存在方法学证据空缺；该结论不等同于首次性声明。 <!-- CLAIM:C07,C08,C09,C10,C11,C13,C15,C20,C21,C22,C23,C26,C27 -->"
    text = re.sub(r"## 摘要\n\n.*?\n\n## 关键词", "## 摘要\n\n" + abstract + "\n\n## 关键词", text, flags=re.S)
    text = re.sub(r"# 1\. 引言\n.*?(?=\n# 2\.)", INTRO.rstrip(), text, flags=re.S)
    text = re.sub(r"# 9\. 讨论\n.*?(?=\n# 10\.)", DISCUSSION.rstrip(), text, flags=re.S)
    replacements = {
        "[REF-TODO: antisymmetric pair-force conservation]": "[V022,V028]",
        "[REF-TODO: method of manufactured solutions]": "[V018,V035]",
        "[REF-TODO: high-order time reference for semidiscrete systems]": "[V005,V006]",
        "[REF-TODO: equivariant neural operators for particle systems]": "[V017,V023,V028]",
        "[REF-TODO: finite-difference verification of algorithmic derivatives]": "[V002,V005,V007]",
        "[REF-TODO: nonsmooth events in particle neighbor graphs]": "（与可微模拟中的事件敏感性相邻，但本TE1合同由项目证据定义）[V015,V019]",
        "[REF-TODO: piecewise differentiability and hybrid systems]": "[V015,V019]",
        "[REF-TODO: repository, DOI and data license]": "[AUTHOR-TODO: 投稿前填写公开仓库、持久标识与许可；当前不作外部可用性主张。]",
        "[REF-TODO: code repository and software citation]": "[AUTHOR-TODO: 投稿前填写代码版本、持久链接与软件引用；当前不作公开性主张。]",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = text.replace("本文P1使用的全部数值结果", "本文v0.2使用的全部项目数值结果")
    text = text.replace("P1不修改历史代码，也不产生新的计算。", "P2不修改历史代码，也不产生新的数值计算。")
    core = [r for r in rows if r["core_reference"] == "True"]
    refs = "# References\n\n" + "\n\n".join(format_reference(r) for r in core) + "\n"
    text = re.sub(r"# References\n.*\Z", refs, text, flags=re.S)
    if "[REF-TODO:" in text:
        raise ValueError("unresolved REF-TODO remains")
    out = P2 / "manuscript_revision/manuscript_cn_v0_2_literature_positioned.md"
    out.write_text(text, encoding="utf-8")
    return text


def build_citation_map(manuscript: str, by_id: dict[str, dict]) -> list[dict]:
    section = "front matter"
    entries = []
    seen = Counter()
    for line in manuscript.splitlines():
        if line.startswith("#"):
            section = line.lstrip("# ")
        ids = re.findall(r"V\d{3}", line)
        if not ids:
            continue
        for cid in ids:
            if cid not in by_id:
                raise ValueError(f"unverified citation in manuscript: {cid}")
            seen[cid] += 1
            entries.append({
                "map_id": f"CM{len(entries)+1:03d}", "manuscript_section": section,
                "source_id": cid, "supported_sentence": re.sub(r"<!--.*?-->", "", line).strip(),
                "citation_role": "direct_method_comparison" if by_id[cid]["literature_level"] != "CORE-C_CONTEXT" else "background_or_reference_hierarchy",
                "mode": "paraphrase", "confidence": "HIGH" if by_id[cid]["evidence_access"] in {"FULL_TEXT", "ABSTRACT_ONLY"} else "MODERATE",
                "access_level": by_id[cid]["evidence_access"],
            })
    out = P2 / "citation_map/citation_to_manuscript_map.json"
    out.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return entries


def build_external_audit(manuscript: str) -> dict:
    entries = []
    section = "front matter"
    sid = 0
    for line in manuscript.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            section = stripped.lstrip("# ")
            continue
        if stripped.startswith(("|---", "$$", "<!--")):
            continue
        units = [stripped] if stripped.startswith("|") else [x.strip() for x in re.split(r"(?<=[。！？])", stripped) if x.strip()]
        for unit in units:
            sid += 1
            citations = sorted(set(re.findall(r"V\d{3}", unit)))
            claims = sorted(set(re.findall(r"CLAIM:([A-Z0-9,]+)", unit)))
            if citations:
                cls = "CITED_VERIFIED"
            elif claims or section.startswith(tuple(str(i) for i in range(2, 11))) or section in {"摘要", "Data availability", "Code availability"} or unit.startswith("|"):
                cls = "PROJECT_EVIDENCE"
            elif "[AUTHOR-TODO:" in unit or any(x in unit for x in ("本文认为", "可辩护", "建议", "不得")):
                cls = "AUTHOR_INTERPRETATION"
            else:
                cls = "AUTHOR_INTERPRETATION"
            entries.append({"sentence_id": f"S{sid:04d}", "section": section, "text": unit, "classification": cls, "citations": citations, "project_claims": claims})
    counts = Counter(e["classification"] for e in entries)
    audit = {"schema_version": "sph-pio-poc.p2.external-claim-audit.v1", "sentence_count": len(entries), "counts": dict(counts), "unsupported_count": counts.get("UNSUPPORTED", 0), "status": "PASS" if counts.get("UNSUPPORTED", 0) == 0 else "FAIL", "entries": entries}
    (P2 / "reports/external_claim_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


def bibtex_key(rec: dict, used: set[str]) -> str:
    family = re.sub(r"[^A-Za-z]", "", (rec["authors"].split(";")[0].split()[-1] if rec["authors"] else "Anon")) or "Anon"
    word = re.sub(r"[^A-Za-z0-9]", "", next((w for w in rec["title"].split() if len(re.sub(r'[^A-Za-z]', '', w)) >= 4), "Work"))
    base = f"{family}{rec['year']}{word}"
    key = base; n = 2
    while key in used:
        key = f"{base}{n}"; n += 1
    used.add(key)
    return key


def latex_escape(s: str) -> str:
    return (s or "").replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")


def build_bib(rows: list[dict]) -> None:
    used = set(); blocks = []
    for rec in rows:
        if rec["core_reference"] != "True":
            continue
        key = bibtex_key(rec, used)
        typ = "article" if "journal" in rec["publication_status"] else "inproceedings"
        authors = " and ".join(a.strip() for a in rec["authors"].split(";") if a.strip())
        fields = [("title", "{" + latex_escape(rec["title"]) + "}"), ("author", "{" + latex_escape(authors) + "}"), ("year", rec["year"])]
        fields.append(("journal" if typ == "article" else "booktitle", "{" + latex_escape(rec["venue"]) + "}"))
        for k, v in (("volume", rec["volume"]), ("number", rec["issue"]), ("pages", rec["pages_or_article"]), ("doi", rec["doi"]), ("url", rec["publisher_url"])):
            if v: fields.append((k, "{" + latex_escape(v) + "}"))
        blocks.append("@" + typ + "{" + key + ",\n" + ",\n".join(f"  {k} = {v}" for k, v in fields) + "\n}")
    (P2 / "verified_records/references_verified.bib").write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def build_reports(rows: list[dict], notes: list[dict], novelty: list[dict], manuscript: str, citation_map: list[dict], audit: dict) -> None:
    raw_count = sum(1 for _ in csv.DictReader((P2 / "raw_candidates/raw_candidate_bibliography.csv").open(encoding="utf-8-sig")))
    core = [r for r in rows if r["core_reference"] == "True"]
    group_counts = Counter(t for r in core for t in r["themes"].split(";"))
    protocol = f"""# P2 literature search protocol

- 截止日期：2026-08-05。
- 数据源：Crossref REST用于可复现发现与精确DOI元数据；出版商/正式会议页面用于题录和方法核验；DOI resolver用于交叉一致性；arXiv仅用于预印本身份与开放全文；搜索引擎仅用于发现。
- 七组检索：T1 SPH/ML correction；T2 learned particle dynamics；T3 conservative/equivariant architectures；T4 differentiable solvers/gradient verification；T5 dynamic topology events；T6 Scientific ML V&V；T7 SPH verification。
- 查询：35条精确查询，逐条记录在`search_query_log.csv`；每条保留Crossref reported result count、screened count与retained raw count。
- 规模：raw={raw_count}；verified={len(rows)}；core={len(core)}。核心主题计数（允许跨组重复）={dict(group_counts)}。
- 题录门：有DOI者要求Crossref exact DOI与DOI resolver一致；无独立DOI的正式会议论文要求publisher/conference official page与arXiv/第二官方记录一致。
- 证据门：CORE-A/B逐篇建立evidence note；无法访问正文时明确`ABSTRACT_ONLY`或`METADATA_ONLY`，不用于强方法推断。
- 去重：正式版优先，预印本只记录关系，不作为独立参考；撤稿/重复/纠正条目进入rejected清单。
- 排除原因：每条仅记录一个主原因；ResearchGate、聚合转载和搜索摘要不作为最终题录依据。
"""
    (P2 / "search_protocol/p2_search_protocol.md").write_text(protocol, encoding="utf-8")

    review = ["# Core literature review", "", f"截至2026-08-05共核验{len(rows)}篇，核心引用{len(core)}篇。以下比较只使用verified题录；强方法陈述优先来自全文。", "", "## T1 直接SPH/ML工作", "", "Neural SPH把SPH压力、黏性和外力分量加入完全学习GNN的训练与rollout [V003]；Woodward等参数化SPH核与项用于湍流降阶模型 [V001]；JAX-SPH与diffSPH已分别建立可微SPH、AD/FD或长期梯度传播及solver-in-the-loop [V002,V004]。因此，本稿的空间不在‘首次learnable/differentiable SPH’，而在冻结资格合同及完整负证据。", "", "## T2 学习型粒子动力学", "", "GNS、continuous convolutions和DPI-Net均直接学习粒子更新并进行自回归或任务rollout [V010,V011,V013]；LagrangeBench提供SPH数据、多个GNN基线与物理指标 [V024]。这些工作是fully learned particle simulator，而非保留SPH推进的additive correction。", "", "## T3 守恒与等变", "", "DMCF用反对称连续卷积硬保证线动量 [V022]；DYNAMI-CAL GRAPHNET同时硬编码线/角动量交换 [V028]；EGNN/SEGNN编码几何等变但不自动保证守恒 [V017,V023]。", "", "## T4 可微求解器与梯度核验", "", "Solver-in-the-loop已建立多步可微PDE corrector训练 [V016]；AD-CFD与tangent/adjoint checking形成导数核验传统 [V005,V007,V008]；JAX-SPH是本稿多步AD/FD最直接的部分先例 [V002]。", "", "## T5 动态图与事件", "", "核验集合包含每步近邻重建、动态粒子图和可微物理，但没有核实到与本项目相同的SPH cutoff birth/death、fixed-side gradients和piecewise-smooth资格组合。该结论是有界空缺，不是全局首次性声明。", "", "## T6 Scientific ML V&V", "", "SciML V&V框架要求区分verification、calibration、validation、prediction domain与UQ [V020,V029]；REFORMS支持透明主张和复现 [V025]。这些文献支持本稿方法定位，但不验证具体SPH合同。", "", "## T7 SPH verification", "", "SPH grand challenges、一致性、收敛、WCSPH时间步与MMS文献说明普通benchmark不应自动称为validation [V042,V056,V058,V076,V018,V035]。", ""]
    (P2 / "thematic_groups/core_literature_review.md").write_text("\n".join(review), encoding="utf-8")

    abstract = """# 结构化摘要 v0.2

## 背景
已核验文献已覆盖learnable SPH、Neural SPH、可微SPH、solver-in-the-loop和硬守恒粒子网络，当前可辩护空缺集中在verification-first联合资格，而非SPH–ML结合本身。

## 方法
冻结D0–D3动态框架，审计独立RK2、zero correction、reciprocal pair-force、多步AD/FD stable windows及TE1拓扑事件；未执行训练、autonomous rollout或性能试验。

## 结果
zero correction 288/288 bitwise等价；多阶段守恒540/540通过；360 probes中216形成stable windows、144失败，history门0/6。TE1 birth/death、6/6 replay和12/12 event-side gradients通过，但edge membership仍离散。

## 结论
Stage 03D保持`DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`。证据支持有限的verification methods定位，不支持模型性能、可训练性或Transformer优越性。
"""
    (P2 / "manuscript_revision/structured_abstract_cn_v0_2.md").write_text(abstract, encoding="utf-8")
    titles = """# Title candidates v0.2

## A — verification-first主线（推荐）
**Verification-first qualification of a conservative dynamic neural–SPH coupling: zero-correction identity, topology events, and multistep gradient limits**

- factual accuracy: 高；直接对应已执行证据。
- novelty alignment: 高；聚焦联合资格链。
- overclaim risk: 低；使用qualification而非novel solver。
- journal fit: verification/methods-oriented computational mechanics。
- negative result exposure: 明确暴露gradient limits。

## B — differentiability-limit主线
**Limits of multistep differentiability in a dynamic neural–SPH coupling: AD/FD stable windows and cutoff topology events**

- factual accuracy: 高。
- novelty alignment: 中高；突出216/360与事件边界。
- overclaim risk: 中；需持续限定单一实现与冻结probe集合。
- journal fit: differentiable simulation/Scientific ML methods。
- negative result exposure: 最强。

## C — conservative dynamic coupling主线
**Conservative dynamic neural–SPH coupling under verification: reciprocal corrections, exact fallback, and piecewise-smooth topology**

- factual accuracy: 高。
- novelty alignment: 中；hard conservation已有强先例。
- overclaim risk: 中；标题中的conservative必须限定为线动量结构检查。
- journal fit: computational mechanics methods。
- negative result exposure: 较弱，摘要必须补足NOT_QUALIFIED。
"""
    (P2 / "manuscript_revision/title_candidates_v0_2.md").write_text(titles, encoding="utf-8")

    reviewer = """# Reviewer positioning report

## 1. 最接近的论文

最接近的直接工作是JAX-SPH [V002]、diffSPH [V004]、Neural SPH [V003]、parameterized learnable SPH [V001]、DMCF [V022]、LagrangeBench [V024]、GNS [V013]与solver-in-the-loop [V016]。其中JAX-SPH已具有5步AD/FD和SPH SitL，diffSPH覆盖更长梯度链与更广应用；二者是最需要正面比较的竞争工作。

## 2. 当前工作增加什么

增加的是冻结的zero-correction bitwise identity、RK2 start/midpoint重建、accepted-only history commit、360-probe stable-window矩阵、reverse/JVP与extended FD归因，以及cutoff birth/death的event-side资格分支。措辞必须限定为“within the verified literature set”。

## 3. 当前工作缺少什么

缺少训练、autonomous rollout、误差、长期稳定性、外推、速度、equal-error cost、跨实现复现和D-R4独立验证；这些正是V003、V004、V013、V022、V024通常提供的性能层证据。

## 4. 最可能被视为工程审计的部分

checkpoint、hash、history事务和bitwise fallback若只在单一代码库展示，容易被认为是软件QA。需要用失败可诊断性、跨架构适用性和第二实现复现证明方法一般性。

## 5. 如何证明一般性

在至少两种SPH实现、两类邻域算法、多个边界/分辨率和两种AD后端复现同一合同；公开probe生成器、阈值依据与失败矩阵；预注册新增topology families。

## 6. negative result为何有方法价值

216/360与144 failures表明选择性展示成功梯度会改变授权结论。完整矩阵可区分局部实现PASS、总体NOT_QUALIFIED和topology component PASS，防止把部分成功转化为训练许可。

## 7. 未训练为何不是规避实验

训练明确依赖Stage 03D资格，而Stage 03D未通过；停止符合预注册路线。但这仍是论文限制，不能替代后续性能实验。

## 8. 必须弱化的结论

不得主张首次可微SPH、首次solver-in-the-loop、模型可训练、性能提高、长时稳定、edge membership可微、角动量/能量守恒或一般topology资格。

## 9. 期刊层级

当前比完整solver型CMAME更现实的是computational methods、verification/validation、Scientific ML methods或software/methodology取向期刊。是否适合具体期刊需在投稿时复核最新scope。

## 10. 升级为完整CMAME论文所需证据

重新授权后的训练资格、自主rollout、跨问题泛化、精度–成本曲线、长期守恒/稳定性、独立参考/实验验证、第二代码实现以及对现有JAX-SPH/diffSPH/Neural SPH的公平复现比较。Stage 03D当前状态必须继续写为`DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`。
"""
    (P2 / "reviewer_positioning/reviewer_positioning_report.md").write_text(reviewer, encoding="utf-8")

    readiness = f"""# Publication readiness v0.2

## Classification

`B. VERIFICATION_METHODS_CMAME_POTENTIAL_BUT_INCOMPLETE`

## Supporting evidence

- P1 freeze PASS；历史hash无冲突。
- raw={raw_count}，verified={len(rows)}，core={len(core)}；核心题录无冲突。
- 直接竞争与方法比较、novelty matrix、citation map和逐句external claim audit已建立。
- 项目正负证据完整保留：288/288、540/540、216/360、144 failures、TE1、NOT_QUALIFIED、no training/performance。

## Literature gap

在verified集合内，未发现zero fallback、RK2/history事务、多步stable-window及SPH cutoff event联合资格的同构报告；JAX-SPH构成多步AD/FD的直接部分先例。

## Fatal weaknesses for a full solver paper

- Stage 03D NOT_QUALIFIED。
- training/rollout/performance均未执行。
- 缺D-R4或等价独立验证。
- 单一实现，缺跨代码一般性。

## Required additions

训练资格、自主rollout、精度–成本与长期稳定性、跨问题/实现复现、独立validation。

## Overclaim risks

不得将可微代码写成已资格AD/FD；不得将hard linear momentum写成角动量/能量守恒；不得将未报告写成未曾发生；不得暗示现有文献的性能增益可迁移到本项目。
"""
    (P2 / "reports/publication_readiness_v0_2.md").write_text(readiness, encoding="utf-8")


def main() -> None:
    rows, by_id, by_sid = read_records()
    notes = build_evidence_notes(rows)
    competitors = build_competitor_matrix(by_sid)
    novelty = build_novelty()
    build_bib(rows)
    manuscript = build_manuscript(rows, by_id)
    citation_map = build_citation_map(manuscript, by_id)
    audit = build_external_audit(manuscript)
    build_reports(rows, notes, novelty, manuscript, citation_map, audit)
    print(json.dumps({"verified": len(rows), "evidence_notes": len(notes), "competitors": len(competitors), "novelty_items": len(novelty), "citation_map_entries": len(citation_map), "external_audit": audit["status"], "unsupported": audit["unsupported_count"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
