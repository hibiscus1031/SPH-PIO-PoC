# Stage 04C Reverse VJP and Forward JVP

All 2592 component comparisons passed the frozen reverse/JVP gate; failures: 0. Each row was independently repeated twice with fresh functional state and explicit math attention. Directional derivatives used the same preregistered normalized Rademacher direction in both modes; JVP was computed by PyTorch's autograd JVP, not finite differences.

This exact agreement does not establish qualification by itself: all 2592 component directions were below the Stage 04C FD-resolution threshold, so the mandatory nonzero-sensitivity evidence is absent.
