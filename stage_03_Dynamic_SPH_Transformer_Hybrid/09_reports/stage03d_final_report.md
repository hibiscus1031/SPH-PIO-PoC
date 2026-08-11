# Stage 03D Final Report

Stage 03C authorization: `DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED`. Contract: `sha256:a506af65ac124f8edf843e507f70c88566852fdfefb017eea127ddbe227fa692`.

Final status: **DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED**.

1. Stage 03C authorization is exact and sole.
2. Historical freeze: 2149 files, zero mismatches.
3. AD/FD contract hash: `sha256:a506af65ac124f8edf843e507f70c88566852fdfefb017eea127ddbe227fa692`.
4. Fixed-topology matrix: 72 arm/case/seed/horizon combinations.
5. Probe objective uses the frozen dimensionless final-state material-coordinate weights.
6. Parameter/input/history probes: 360 required rows with exact parameter paths and deterministic directions.
7. Stable epsilon windows: 216/360.
8. Horizons 1/2/4/8 are all covered.
9. Graph-sequence exclusions: 0.
10. Accepted history commit equals K; midpoint commit equals zero; length remains four.
11. Conservation over time: 540/540 per-stage correction residual gates pass; combined gate C is false only because the REFERENCE_PREHISTORY stable-window audit failed.
12. REFERENCE_PREHISTORY pass: 0/6.
13. TE1: r(s)=0.65+0.035 cos(2 pi s), two tagged particles only.
14. Exact event times: birth 0.25; death 0.75.
15. Analytic side margin: 0.00021475596272040666; observed float64 match passes.
16. Dense scan: 4097 points x 3 repeats; exactly one birth and one death.
17. Stage replay pass: 6/6.
18. Fixed-side gradients pass: 12/12.
19. Cross-event boundary is diagnostic and classified piecewise smooth with a discrete graph change.
20. Pair-force jumps are finite, bounded by frozen tanh limits, conservative, and explicitly registered.
21. Empty nonself graph has exact-zero pair aggregation and no synthetic self pair.
22. AD, FD paths, graphs, histories, event sequences, and parameter bases meet deterministic-repeat gates.
23. Resource hard gates: True; CPU float64; N16 K8 D3 audit-only AD completed.
24. Stage 03E authorization: NONE.
25. optimizer steps = 0.
26. training runs = 0.
27. No rollout-performance, solver-improvement, or benchmark claim is made.
28. No differentiable-neighbor-search or differentiable-edge-existence claim is made.
29. Stage 01/02/03A-C histories are unchanged; Stage 01 remains V2_QUALIFICATION_FAIL, Stage 01H FINITE_RESOLUTION_DOMINANT, viscosity operator form NOT_CONFIRMED, and the Stage 02 static route TERMINATED.
