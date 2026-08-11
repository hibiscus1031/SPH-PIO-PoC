# Stage 04B Reuse Contract

Stage 05 inherits Stage 04B assets read-only. The immutable roles are:

| Role | Lineages |
|---|---|
| TRAIN | `LCDF_01`, `LCDF_04`, `LCDF_05`, `LCDF_06`, `LCDF_07`, `LCDF_08` |
| VALIDATION | `LCDF_02`, `LCDF_09` |
| SEALED_TEST | `LCDF_03`, `LCDF_10` |

The ten formula components, 6/2/2 assignment, zero cross-role leakage, formula/state/target seals, trajectory identities, fixed-topology qualification, and analytic/DOP853 qualification remain unchanged. Stage 05A reads only public contract and manifest metadata and decodes no payload.

No failed family may be replaced, no new family may substitute for an observed failure, and no role may be swapped.
