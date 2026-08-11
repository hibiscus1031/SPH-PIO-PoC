# RK2 stage semantics

The baseline integrator is explicit midpoint/RK2 for the coupled `(x,v,rho)` state. Define `F(S,history)=(v, a_SPH+a_theta, C_SPH)` with pressure recomputed from density before every RHS evaluation.

## A — start

From accepted `S^n`, recompute EOS, rebuild reciprocal `G^n`, construct `z^n`, evaluate temporal state, evaluate baseline and correction terms, and form `k1=F(S^n)`. No history mutation occurs.

## B — provisional midpoint

Construct `S^{n+1/2}=S^n+(dt/2)k1`; recompute its EOS; independently rebuild `G^{n+1/2}`; construct an ephemeral midpoint token; evaluate the temporal module using accepted prior history plus that token; evaluate midpoint baseline/correction; form `k2=F(S^{n+1/2})`. The midpoint is one RK stage, not a physical time step.

## C — accepted state

Compute `S^{n+1}=S^n+dt*k2`, recompute EOS, run finite/safety checks, and accept atomically. Only after acceptance is `z^{n+1}` constructed from the accepted state and committed once to history. A rejected/failed step commits nothing. Every quantity's start/midpoint/accepted tag must be explicit in future records.
