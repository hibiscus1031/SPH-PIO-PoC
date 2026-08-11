# Stage 06C Execution Control

Execution is locked to one CPU process, float64, explicit `SDPBackend.MATH`, and the frozen order `D1_seed20600611, D1_seed20600612, D1_seed20600613, D2_seed20600611, D2_seed20600612, D2_seed20600613, D3_seed20600611, D3_seed20600612, D3_seed20600613`. AdamW, scheduler, clipping, zero-grad, batch order, 1500-update budget, 20-update evaluation/checkpoint cadence, selection at update >=320, and early stopping are consumed from Stage06B without reinterpretation. Scientific retry, replacement seeds, parallel runs, rollout, and SEALED_TEST access are forbidden.

Ready for formal steps: **True**
