# Stage 04A — Local-Causal Dynamic Training Hypothesis and Prospective Qualification Contract

Stage 04 introduces a new scientific hypothesis: a conservative dynamic neural-SPH model may be trained through task-aligned one-step or short-window RK2 state-transition supervision without relying on a fully qualified long-chain `K=8` reverse-mode gradient. This is a prospective hypothesis and contract, not evidence that trainability, rollout stability, or solver utility has been established.

The formal Stage 04 v0.1 training horizon is `K=1`. A sample supplies three reference states strictly earlier than the origin and the current reference state `S^n`, giving accepted history length `H=4`. The model advances one complete RK2 step, rebuilds the midpoint graph, uses a noncommitted ephemeral midpoint token, and predicts `S_theta^(n+1)`. The only task target is the reference accepted state `S_ref^(n+1)` through the state loss defined in `01_training_formulation/one_step_rk2_loss.md`.

Stage 04A is contract-only. It creates no trajectory, test payload, checkpoint, optimization step, parameter update, training run, rollout, or model-performance result. Stage 01–03 artifacts are read-only historical evidence. In particular, Stage 03C, Stage 03D, Stage 03D-R, Stage 03D-S, the topology-component verdict, and `Stage 03E authorization=false` remain unchanged.

The next and only authorized stage is **Stage 04B — New Dynamic Reference-Family Pool and Lineage Qualification**. Stages 04B, 04C, and 04D must complete before any formal training in Stage 04E.

Final status: `LOCAL_CAUSAL_TRAINING_HYPOTHESIS_CONTRACT_COMPLETE`.
