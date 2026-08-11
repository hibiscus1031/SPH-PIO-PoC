# Option A：Stage 00–04 单篇整合论文

[PUBLICATION_RECOMMENDATION] 只有Stage04E/F/G强通过、独立验证与refinement充分、D3相对D0/D1/D2存在稳定且等误差优势时才优先。

- 主线：V&V → reference → conservative architecture → dynamic implementation → training → rollout → independent validation → cost。
- 最强贡献：端到端verification-first资格链，同时保留static与gradient负结果。
- 所需Stage04：task-aligned gradients、训练资格、autonomous rollout、独立验证、refinement、cost全部形成机器证据。
- CMAME潜力：[INFERENCE] 高，但篇幅和叙事复杂度最高；需将完整失败矩阵移入补充材料，正文仍必须可见关键负结果。
- 风险：Stage04任何关键门不通过都会使“完整solver论文”主线断裂；不可用局部训练曲线掩盖Stage01/02/03失败。
