# Stage 02J-R Leakage and Split

Lineage preflight showed four potentially disconnected components if all families qualified. Dataset leakage is evaluated only over materialized, qualified records. Because none of the three new families reached 6/6 attribution, the controlled corpus still contains only `FAMILY_PV_EXISTING` and its original five-node leakage component.

Qualified dataset component count: 1. No cross-family leakage edge was deleted, and shared infrastructure was not treated as lineage.

The preregistered roles remain unchanged:

- future train: PV existing + CROSSMODE_A;
- future validation: DIAGONAL_B;
- future test: MIXED_C.

The formal split fails because CROSSMODE_A, DIAGONAL_B, and MIXED_C are unqualified and absent as records. A train family was not substituted for validation/test, no roles were changed, and no split manifest or record assignment was created.

