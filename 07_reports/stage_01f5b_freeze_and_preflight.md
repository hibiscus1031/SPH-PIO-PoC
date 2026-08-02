# Stage 01F5B freeze and preflight

Stage 01F5-Q evidence commit `8ab58b8647c1dd1e5cfe71a77cf6ec71c93a1484`, unique status `FORMAL_SPACE_EXECUTION_BUNDLE_READY`, and annotated tag `stage-01f5q-formal-space-execution-bundle-ready` were verified. The tag points exactly to the evidence commit. The final report, horizon amendment, 21 common times, space binding, bundle v3, 69/69 dry-resolution audit, evaluator, prior manifest, and v2 run matrix all match their frozen SHA-256 values.

The numerical source identity is commit `38487d66b40fa2c8dd65eb7aa6c279da4a8e5e2c`. All 103 tracked files under `01_solver` and `05_metrics` match the frozen manifest; the canonical source-tree SHA-256 is `85000dc890ba2525d20fd75e46c20b591948fd3e17ae19b8cb690d6da34f4c09`. This includes pressure, viscosity, density, EOS, RK2, source adapter, neighbor search, MMS-A, MMS-B, and semidiscrete reference RHS components.

The first preflight attempt used the non-frozen base Python and is retained at `results/preflight_audit.json` with SHA-256 `74f824122ba17577630c0f0d926745984c87a361e1d2f9e0e0139932afffd2bf`; it failed only because `diffSPH` was absent. No numerical run was started.

The authoritative retry used `/opt/miniconda3/envs/sph-pio-poc/bin/python` (Python 3.12.13). Complete repository pytest passed `296/296`. All nineteen recorded preflight checks passed, including frozen manifest, bundle, 69-row matrix, 69/69 dry resolution, numerical source tree, canonical T/P/H/S/safety hashes, unique run IDs/output directories, empty outputs, scalar-only parent schema, solver-free child launch/exit smoke, and disk capacity. Its audit is `results/preflight_audit_attempt2.json`, SHA-256 `67e2699c493bc7758e9a9d068923c4990d9cb3a8ea1afbdd384dd2b30646cc0f`.

Before the first trajectory, configuration, worker semantics, coordinator, analyzer, evaluator, and report generator are sealed in `manifests/preexecution_artifact_manifest.csv`. The coordinator rechecks every hash before every numerical run. Existing numerical evidence is never overwritten or rerun under the same run ID.
