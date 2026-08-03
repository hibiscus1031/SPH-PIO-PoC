# Stage 01G — Read-only V2 evidence map

Stage 01G creates no V2 status. This map identifies the evidence that a later execution stage must assemble without rewriting its sources.

| V2 evidence block | Read-only evidence |
|---|---|
| V1 / code verification | Stage 01C; Stage 01F; Stage 01F2; Stage 01F3-R |
| Solution verification | Stage 01F5B T/P/H/S; reference qualification; determinism; N64 branch; hard safety |
| Independent validation | Future shear-wave evidence; future acoustic-wave evidence |
| Uncertainty | Reference; time step; spatial envelope; acoustic amplitude/model form; determinism; resource; GCI limitation |

A later stage may declare `V2_QUALIFICATION_PASS` only if SHEAR1–SHEAR8, ACOUSTIC1–ACOUSTIC10, frozen Stage 01F5B identity, and all hard-safety gates pass, and both uncertainty and provenance are complete. Any core independent benchmark gate failure yields `V2_QUALIFICATION_FAIL`. Missing necessary evidence yields `V2_QUALIFICATION_EVIDENCE_INCOMPLETE`.

## Domain of validity

The preregistered domain is limited to 2D periodic, smooth weakly compressible, low-Mach flows using Wendland C4, the frozen EOS and pressure/viscosity operators, CPU float64, and the tested resolution/support range (N 24–48 with H/dx 4.5–5.5, plus the specified N32 time-step isolation).

Explicit exclusions are free surfaces, solid-wall boundaries, shocks, multiphase flow, FSI, turbulence, 3D, and any learned corrector.

Even a future V2 pass does not automatically start V3 or Stage 02 and does not authorize model training or label generation.
