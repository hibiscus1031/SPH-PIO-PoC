# Stage 01F3B semidiscrete RK2 time order

## Method

The production sparse RK2 trajectory was compared with the qualified Stage 01F3-R dense all-pairs DOP853 reference for the same semidiscrete SPH system. Both MMS solutions used N16, `H/dx=4.06155281280883`, `t_final=0.01`, five RK2 steps from `1e-3` through `6.25e-5`, and 11 common physical times. Integrated trajectory RMS is the preregistered order-fit metric. Endpoint error, combined-state L2 and successive-dt self-difference were also retained.

## Results

| Solution | Field | fitted order | local orders coarse→fine | finest/coarsest | reference uncertainty | valid dt points |
|---|---|---:|---|---:|---:|---:|
| MMS-A | position | 1.9739 | 1.9405, 1.9714, 1.9860, 1.9931 | 0.004213 | 1.639e-14 | 5 |
| MMS-A | velocity | 2.0121 | 2.0260, 2.0137, 2.0070, 2.0036 | 0.003772 | 1.942e-13 | 5 |
| MMS-B | position | 1.9669 | 1.9247, 1.9636, 1.9821, 1.9911 | 0.004300 | 1.743e-14 | 5 |
| MMS-B | velocity | 2.0068 | 2.0147, 2.0076, 2.0039, 2.0020 | 0.003831 | 1.647e-13 | 5 |

All 10 formal trajectories passed source, conservation, topology, finite-state and resource gates. Every RK2 error exceeded 20 times its relevant dense-reference uncertainty, so no point was excluded by the reference floor. The median of the finest three local orders is between 1.982 and 2.007.

SD1–SD6: **PASS for MMS-A and MMS-B**. Continuous MMS exact error was not used to establish this RK2 order.
