# Temporal history semantics

Stage 03B `DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE` is the sole authorization. CPU float64 was used; optimizer steps and training runs are both zero.

D2 uses a shared GRUCell and D3 uses a per-particle length-four causal Transformer. Main-gate initialization repeats the initial accepted token; reference prehistory reads only three strictly earlier frames. Start and midpoint commit zero times; accepted steps commit once; rejection commits zero. Machine history gate: PASS.
