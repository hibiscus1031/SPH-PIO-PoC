# Stage 02J-R Target Qualification

Fifteen preregistered target candidates were constructed using

\[
\Delta a=a_{FOURIER}-a_{SPH},\qquad y=m\Delta a,
\]

with sign `a_reference_minus_a_sph`. Every candidate retains state/config/graph hashes, SPH/Fourier/analytic fields, reference difference, nodal force, L2/Linf and quantiles, graph TV, preregistered-mode Fourier signature, deterministic repeat, and separate uncertainty buckets. No edge-pair target or incidence pseudoinverse label was stored.

| family | target L2 range | target Linf range | resolution endpoint ratio | max PCG64-null ratio | support ratio | support status |
|---|---:|---:|---:|---:|---:|---|
| CROSSMODE_A | 0.1699–0.4632 | 0.2767–0.7068 | 0.3668 | 0.8236 | 1.6257 | PASS |
| DIAGONAL_B | 0.1878–0.5050 | 0.3122–0.7913 | 0.3720 | 0.8577 | 1.5100 | PASS |
| MIXED_C | 0.3529–0.8660 | 0.5188–1.2142 | 0.4075 | 1.0055 | 1.1707 | PASS |

For every family, endpoint magnitude, adjacent preregistered-mode direction cosine, relative-neighbor variation, physical-gradient-scale CV, and all support gates pass. However, the frozen Stage 02I PCG64 permuted-null gate requires every resolution level to have a ratio at most `0.8`. Each family has at least one failure.

Consequently all 15 cases have a 5/6 attribution vector rather than 6/6. Each complete five-case family remains diagnostic. No threshold was lowered, no cyclic-roll null was substituted, and no case/resolution/support was removed, replaced, or added after observation.

