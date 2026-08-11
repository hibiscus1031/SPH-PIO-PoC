# Stage 03D-S — Manuscript readiness

| Direction | Focus | Readiness | Evidence assessment | Journal fit |
|---|---|---|---|---|
| Paper A | 完整动态 SPH-Transformer hybrid solver | NOT_READY | 缺少训练、rollout 与独立性能验证；不能形成完整 solver-performance 论文。 | 当前不适合以完整求解器主张投稿 CMAME。 |
| Paper B | verification-first conservative dynamic neural-SPH coupling | MOST_DEFENSIBLE_BUT_INCOMPLETE | 创新点可放在 verification-first 分层、bitwise zero correction、结构守恒、TE1 事件边界和透明负梯度证据；必须把 multistep limitation 置于主文。 | 主题与 CMAME 的 meshless、fluid mechanics、physically based ML 范围相符，但当前需增强方法普适性与独立验证后才更有竞争力。 |
| Paper C | limits of multistep differentiability verification in dynamic graph particle solvers | POTENTIAL_METHODS_NOTE | 可围绕 backend sensitivity、FD conditioning、history attenuation、piecewise topology 与 negative-result value；需证明诊断框架超出单个 PoC。 | 若形成通用、可复现实验方法并覆盖多实现/问题族，才可能与高水平计算方法期刊匹配。 |

## Direct answers

1. A complete full-solver paper cannot yet be formed because training, rollout and independent performance evidence are absent.
2. The defensible route is a verification/methods paper (Paper B), potentially with Paper C's differentiability-limit diagnostics.
3. CMAME currently covers meshless methods, fluid mechanics and physically based machine learning, so the topic is in scope; the present evidence package is not yet ready for a full-solver CMAME claim and would need broader method depth and independent validation.
4. The three core missing evidence classes are: formal dynamic training qualification; controlled/autonomous rollout performance and stability; independent D-R4-equivalent validation and cross-problem generality.
5. Main text should retain the complete verification chain, all 360 outcomes including 144 failures, topology boundary and explicit claim map.
6. Supplementary material should contain full matrices, extended FD, reverse/JVP, history/horizon traces, topology replay and hash/resource audits.
7. Machine-specific debug traces and unqualified post-hoc comparisons remain internal only.

Official scope source checked 2026-08-05: https://www.sciencedirect.com/journal/computer-methods-in-applied-mechanics-and-engineering
