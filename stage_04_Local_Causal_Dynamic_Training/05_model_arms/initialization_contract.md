# Initialization and comparison contract

Every formal D1, D2, and D3 training run begins from a fresh initialization. Stage 02 and Stage 03 checkpoints, parameters, optimizer states, normalizers fitted to their payloads, and learned embeddings are prohibited initialization sources.

Stage 04D must preregister initialization distributions, seed schedule, parameter-dtype/device creation, bias rules, recurrent-state initialization, and any architecture-appropriate scale handling. Seeds must be paired or otherwise balanced prospectively without forcing architectures to share incompatible parameter tensors.

Fair comparison requires the same legal token information, common pair-head implementation, qualified trajectory split, accepted-state loss, optimizer budget, checkpoint-selection rule, and formal environment. Parameter count and compute differences must be reported rather than secretly compensated after results.

No arm is designated expected winner. Selection and reporting include all preregistered seeds and failures. Failed runs cannot be replaced with favorable reseeding outside the registered policy.
