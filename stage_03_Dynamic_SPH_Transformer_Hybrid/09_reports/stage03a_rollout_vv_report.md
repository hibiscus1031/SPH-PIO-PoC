# Stage 03A rollout and V&V report

Formal rollouts may use three reference states strictly before the origin as warm-start history. Thereafter `teacher_forcing_after_start=false`: the model self-feeds accepted predicted states. The horizon order is fixed `K=1 -> 2 -> 4 -> 8`, each gated before the next; failures cannot be removed and short-horizon success cannot replace longer qualification.

Future loss is a horizon-weighted sum of graph-balanced velocity and density errors plus periodic minimum-image position error. Pressure is EOS-derived. One-step acceleration, energy, torque, and power are diagnostics. Conservation/antisymmetry penalties are prohibited. Numerical loss weights await Stage 03F preregistration and cannot be tuned after results.

The V&V ladder is D0 specification; D1 zero equivalence; D2 dynamic components; D3 1/2/4/8-step AD/FD; D4 controlled fitting; D5 autonomous validation; D6 time/space/support solution verification; D7 independent physical validation; and D8 equal-error cost/utility. Levels cannot be skipped.

AD/FD covers a generic network parameter, D3 attention-logit parameter, pair-head parameter, initial velocity/density, and hidden token with at least three epsilons per horizon; topology events are separate. Stability uses the eleven frozen `DYN_*` codes and retains first-step hashes/metrics. Refinement paths are dt/dt/2/dt/4, at least three N, at least three H/dx, and all horizons through long autonomous rollout. No rollout occurred in Stage 03A.
