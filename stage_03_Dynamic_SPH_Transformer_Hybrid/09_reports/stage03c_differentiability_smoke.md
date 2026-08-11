# Differentiability plumbing smoke

Stage 03B `DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE` is the sole authorization. CPU float64 was used; optimizer steps and training runs are both zero.

Six fixed-topology one-step autograd runs covered D1/D2/D3 on D-R1/D-R3 N8. Parameter, initial velocity/density, D2 initial hidden, D3 historical token and D3 attention-logit gradients were required finite, nonzero and deterministic. Gate: PASS. Edge indices/sort/existence carry no gradients. Finite differences, multistep AD/FD, optimizers and parameter updates were not executed.
