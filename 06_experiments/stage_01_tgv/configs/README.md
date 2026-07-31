# Stage 01 experiment configurations

Canonical configurations live in `01_solver/configs/`:

- `tgv_cpu_16.yml`, `tgv_cpu_24.yml`, `tgv_cpu_32.yml`
- `tgv_mps_16.yml`, `tgv_mps_32.yml`

Every invocation writes a resolved JSON snapshot beside the untracked raw
trajectory.  That snapshot adds the project Git hash, the official diffSPH
example commit, installed package versions, installed-source tree hashes,
particle count, total steps, fallback settings, and the exact run identifier.
The two deterministic repeats use `--run-id run-1` and `--run-id run-2`.

The sustained test reuses `tgv_mps_32.yml` with
`--run-id stability-600s --sustain-seconds 600`.
