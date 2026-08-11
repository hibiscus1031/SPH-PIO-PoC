# Stage 02L — Optimizer and schedule

Prospective optimizer: AdamW (`lr=1e-3`, betas `0.9/0.999`, epsilon `1e-8`, weight decay `1e-6`), global gradient norm cap 1.0. Schedule: 50-update warmup then cosine decay to `1e-5`, maximum 1000 updates. No grids, restarts or extensions. Optimizer and scheduler counters remain zero.
