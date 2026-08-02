# Stage 01F3B numerical uncertainty assessment

## Time reference and timestep floors

The dense semidiscrete reference RMS uncertainty is `1.64e-14/1.94e-13` for MMS-A position/velocity and `1.74e-14/1.65e-13` for MMS-B. Every formal RK2 time error exceeded 20 times its relevant floor; no time-fit point was excluded. The N32 space-step isolation changed the four primary exact errors by at most `5.3e-6` relatively, so formal spatial errors are not timestep-limited at the 10% gate.

MMS-B independent continuous trajectory baseline/tighter differences remained below the reported trajectory-reference bound and far below the observed spatial platform.

## Spatial path and GCI

All four primary errors are monotone on the increasing-neighbor path, but local orders are not uniformly stable within 25% for position, density or pressure. Their observed-order/GCI entries therefore state **GCI not justified**.

Velocity meets the preregistered local-order and selected-triplet sensitivity conditions for each MMS solution; its path-specific global order is about 1.45. The resulting fine-grid GCI is about 142%, a very broad interval, and applies only to the preregistered increasing-neighbor consistency path, not to a fixed-stencil single-h family. No GCI is shared across variables.

## Remaining uncertainty and limitation

Continuous velocity exact errors approach the spatial platform from below, causing a tiny increase under temporal refinement: 0.01195% for MMS-A and 0.00312% for MMS-B. Although self-differences contract by roughly two orders of magnitude and the space matrix improves cleanly, the zero-tolerance CT2 inequality is formally violated. This limitation determines the final FAIL status and is not reclassified as a reference, source, conservation, topology, resource or determinism failure.
