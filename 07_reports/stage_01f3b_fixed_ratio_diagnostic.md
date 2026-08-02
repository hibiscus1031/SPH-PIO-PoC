# Stage 01F3B fixed-ratio diagnostic

This diagnostic uses `H/dx=4.5`, N16/24/32/48 and the same frozen `dt_space`. All 8 trajectories passed hard gates. It does not replace the formal increasing-neighbor path.

For MMS-A, density L2 changes `2.664e-4→2.091e-4→1.895e-4→1.799e-4`; for MMS-B it changes `2.688e-4→2.119e-4→1.926e-4→1.831e-4`. The N32→N48 improvement is small compared with the formal path, and initial kernel-density errors show the same floor. This identifies fixed-neighbor kernel-density quadrature as the dominant platform mechanism.

Velocity and position continue to improve, while pressure follows density through the frozen EOS. N48 fixed-ratio edge counts are 158,976 initially for MMS-A and 152,448 at the final MMS-B checkpoint, below the formal-path costs. MMS-B topology event counts increase from 384 at N16 to 3,264 at N48, with zero structural defects.
