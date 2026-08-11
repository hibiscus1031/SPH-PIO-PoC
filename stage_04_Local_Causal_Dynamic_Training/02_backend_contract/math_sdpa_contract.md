# Fixed math-SDPA contract

Formal D3 gradient qualification and any downstream D3 hard evidence must use PyTorch scaled-dot-product attention under an explicitly selected `SDPBackend.MATH` implementation. Flash SDPA, memory-efficient SDPA, backend auto-selection, and silent fallback are prohibited.

The run must enter an explicit math-only backend context and assert the selected backend before the first forward pass. If math selection cannot be confirmed, the run is invalid for hard evidence and must stop or be labeled diagnostic only. A backend label inferred only from hardware or tensor dtype is insufficient.

Backend identity must be serialized into every later checkpoint and run manifest and incorporated into the canonical result hash. At minimum, identity includes framework/version, backend enum/name, device, dtype, attention implementation entry point, deterministic-mode settings, and the flags showing flash and memory-efficient paths disabled. Resume must reject a checkpoint whose recorded formal backend identity differs from the active environment.

Other attention backends may be examined only as explicitly segregated diagnostics. They cannot qualify D3, choose epsilon, set thresholds, select checkpoints, repair Stage 03D evidence, or contribute to formal cross-arm claims. No backend comparison is executed in Stage 04A.
