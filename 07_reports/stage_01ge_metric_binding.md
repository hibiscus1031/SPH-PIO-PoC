# Stage 01G-E metric and gate binding

## Authoritative sources

The unique threshold source is frozen Stage 01G configuration SHA-256 `5025492f21f6b00c33ebc9533d27fbf632668945cba6a6a4a10df115c9ff1fe1`. The unique metric-contract source is `stage_01g_validation_metrics.md`, SHA-256 `655bfceb2339adfd07d9a4c724cbb66410210a76b865f6edcc0d6a74c7b9b042`.

The gate APIs accept only `run_results`; they expose no threshold/config override and contain no adaptive threshold path. The machine-readable binding is `results/stage01ge_metric_binding.json` and is exactly reproducible from `gate_rules.metric_binding()`.

## Normalization freeze

- Field norms are particle-volume weighted; vector components are combined before L2/Linf.
- Position uses minimum-image error on side length 2. Relative position L2 uses exact displacement L2, excluding the zero-displacement initial time.
- Shear amplitude is a weighted projection onto `sin(k_s*y_reference)`; decay is a fixed log-amplitude linear fit.
- Acoustic fundamental amplitudes use weighted spatial projection and fixed temporal quadrature.
- Acoustic density/velocity signal L2 is a full space-time error norm divided by the independent space-time reference signal norm. This avoids inventing a denominator at the one-period zero-velocity endpoint.
- Acoustic transverse leakage uses the reference velocity-signal norm. There is no direct or hidden epsilon denominator.
- Spatial gates use strict N24 > N32 > N48 comparisons. Time isolation divides by the half-dt metric as frozen.

All SHEAR1–SHEAR8, ACOUSTIC1–ACOUSTIC10 and hard-safety limits are bound. Metric binding: **PASS**.
