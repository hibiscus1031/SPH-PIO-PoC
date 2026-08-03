# Stage 01G Execution Preflight v2 — Run Matrix Audit

The authoritative run matrix SHA-256 is `ad79c1e7ea7af026222accc4ea8adff716c067b379954ca77697e475e5e0ba12`. It contains exactly 12 preregistered runs, 12 unique run IDs, and 12 unique future output directories.

## Shear runs (5)

- `g_shear_n24`
- `g_shear_n32`
- `g_shear_n48`
- `g_shear_n32_dt_half`
- `g_shear_n48_rep2`

## Acoustic runs (7)

- `g_acoustic_e5e3_n24`
- `g_acoustic_e5e3_n32`
- `g_acoustic_e5e3_n48`
- `g_acoustic_e5e3_n32_dt_half`
- `g_acoustic_e5e3_n48_rep2`
- `g_acoustic_e2p5e3_n48`
- `g_acoustic_e1e2_n48`

Every row remains `PREREGISTERED_NOT_EXECUTED`. Each future output directory is absent or empty; trajectory, checkpoint, and reference-data counts are all zero. No run was added, removed, renamed, or executed.

Run matrix audit: **PASS**.
