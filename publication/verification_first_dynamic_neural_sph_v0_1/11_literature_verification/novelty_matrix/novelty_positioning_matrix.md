# Novelty positioning matrix

限定语：以下判断仅针对截至2026-08-05完成题录与正文核验的94篇集合。

| ID | 结论 | 证据与边界 |
|---|---|---|
| N1 | `SUPPORTED_NOVELTY_GAP` | V001–V004提供learnable/differentiable SPH直接先例，但在核验全文中未发现以bitwise baseline identity作为正式退化合同。 仅限截至2026-08-05的94篇verified集合；不得写为从未有人做过。 |
| N2 | `SUPPORTED_NOVELTY_GAP` | V002、V003、V004、V013涉及多步粒子动态图或可微SPH，但未核实到该二者联合的事务式合同。 属于合同组合的证据空缺，不主张单个工程做法首次出现。 |
| N3 | `PARTIAL_PRECEDENT` | V002明确比较5步AD与FD，但使用一个预选epsilon；V007等提供AD-CFD验证背景。未见与本项目相同的相邻epsilon稳定窗和完整probe矩阵。 JAX-SPH是直接先例，故不能写成首次多步AD/FD。 |
| N4 | `SUPPORTED_NOVELTY_GAP` | 核验集合含reverse AD、adjoint checking及可微求解器文献，但未发现四类诊断在同一dynamic neural-SPH资格链中联合报告。 组合证据空缺；各诊断单独均有方法学先例。 |
| N5 | `SUPPORTED_NOVELTY_GAP` | V002/V004使用动态粒子邻域，V015/V019提供非光滑/可微模拟背景；核验正文未发现SPH cutoff事件的同构资格矩阵。 不能外推到所有动态图或混合系统。 |
| N6 | `PARTIAL_PRECEDENT` | V003、V024等报告rollout不稳定/局限，V025/V029倡导透明报告；未找到与360-probe失败矩阵同规模、同合同的直接先例。 是否置于‘主论文’受版本与补充材料边界影响，不能作全局否定。 |

建议正文措辞：‘据我们所知，在本次已核验文献集合内，尚未发现……的联合、可审计证据。’禁止使用 FIRST、NOVEL 或 UNPRECEDENTED。
