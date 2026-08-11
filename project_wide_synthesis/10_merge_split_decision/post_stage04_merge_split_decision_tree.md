# Stage 04后合并/拆分决策树

| Scenario | 条件 | 建议 | 信心 | 所需证据 | 理由 | 风险/期刊 |
|---|---|---|---|---|---|---|
| 1 | Stage04C task-aligned gradient仍未资格化 | C | high | task-aligned gradient machine gates | 独立投稿Stage00–03 verification paper | 低：边界清楚 | specialist/high-impact methods conditional |
| 2 | Stage04C通过但Stage04E训练未资格化 | C or B(Paper1 first) | high | gradient PASS + training FAIL evidence | Stage00–03为主；Stage04作限制/技术报告 | 中 | methods journal |
| 3 | Stage04E训练通过但Stage04F autonomous rollout未通过 | B | medium | training gates + failed rollout | Paper2仅能是短窗学习论文；不宜完整CMAME主线 | 中高 | specialist ML/physics methods |
| 4 | Stage04E/F通过但独立验证或refinement不足 | B, Paper1 first | high | rollout PASS; validation/refinement incomplete | 延后性能论文 | 中 | Paper1 methods; Paper2 pending |
| 5 | Stage04E/F/G强通过且D3稳定独立等误差优于D0/D1/D2 | A evaluate first | medium | training+rollout+validation+refinement+cost | 评估完整CMAME整合稿 | 高：篇幅/叙事 | CMAME/JCP potential |
| 6 | Stage04成功且Stage00–03框架跨模型/跨问题一般 | B | medium | cross-model/cross-problem evidence | 仍可拆分方法与性能，但严控重叠 | 中 | two high-level papers possible |
