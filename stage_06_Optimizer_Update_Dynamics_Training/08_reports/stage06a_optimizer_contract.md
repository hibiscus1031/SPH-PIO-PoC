# Stage 06A optimizer contract

The sole candidate is AdamW: betas `(0.9, 0.999)`, eps `1e-12`, weight decay `0`, AMSGrad disabled, and global gradient clip `1.0`. The frozen qualification ladder is `1e-5, 3e-5, 1e-4, 3e-4, 1e-3`. Each LR starts from an independent fresh clone and zero moment state. No optimizer or LR is selected for formal training.
