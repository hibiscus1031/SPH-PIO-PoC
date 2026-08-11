# Stage 02M-Q — Conditioning execution

Conditioning snapshots were retained for updates 0, 1, 10, 50, 100, selected checkpoint and terminal checkpoint in all nine runs: **True**. Each snapshot records parameter/module gradient RMS, Adam moment scale, epsilon-dominated fraction, zero weight-decay domination, effective-update/parameter ratio, and coefficient RMS/saturation. Selected and terminal gradients were diagnostic recomputations with zero optimizer steps.
