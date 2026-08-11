# Stage 02M-P — Optimizer conditioning contract

唯一 optimizer 为 AdamW：lr=1e-3、betas=(0.9,0.999)、epsilon=1e-12、weight_decay=0、global norm clip=1。相对 v0.1，仅把 epsilon 从 1e-8 改为 1e-12、weight decay 从 1e-6 改为 0，并用 train-only a_sup 替代 a0=400 的 loss scale。无 optimizer/epsilon/loss-scale/weight-decay grid，无 architecture-specific optimizer、restart 或 budget extension。
