# Stage 02J-R Family Separability Preflight

The preflight executed before any new acceleration or target evaluation and read the frozen Stage 02B split/leakage contract directly.

Four distinct identities were checked: `FAMILY_PV_EXISTING`, `FAMILY_CROSSMODE_A`, `FAMILY_DIAGONAL_B`, and `FAMILY_MIXED_C`. Each has its own family ID, initial-condition lineage, solution family, formula/source lineage, and derivative lineage where applicable. There is no parent trajectory, shared seed, restart, resample, or direct source-record ancestry across families.

The following shared infrastructure was explicitly classified as non-lineage: EOS implementation, baseline SPH code, Fourier implementation, periodic domain, target schema, and serializer. The machine implementation does not connect families merely because they share reference code.

Result: zero cross-family leakage edges and four potentially separable family components. The Stage 02B contract was not modified. This preflight establishes possible lineage separation only; it does not waive later reference, attribution, conservation, or record-materialization gates.

