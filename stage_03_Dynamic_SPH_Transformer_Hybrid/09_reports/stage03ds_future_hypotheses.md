# Stage 03D-S — Future hypotheses (design only)

| ID | New hypothesis | Required route | Executed in Stage 03D-S |
|---|---|---|---|
| H1 | 不依赖长链 reverse-mode 的局部 one-step/短窗目标可获得可资格化训练信号。 | new Stage 04 | False |
| H2 | 显式可微邻域近似或连续邻接权重可重定义拓扑可微边界。 | new Stage 04 with a new topology contract | False |
| H3 | 离散伴随、自定义 JVP 或统一 math-attention backend 可改善多步梯度资格。 | new Stage 04 with new implementation and AD/FD contracts | False |
| H4 | 非学习或解析型动态保守修正可在不依赖端到端训练时建立动态证据。 | new Stage 04 | False |

No branch is a direct Stage 03E continuation. Each requires a new Stage 04 hypothesis and a new contract before any computation.
