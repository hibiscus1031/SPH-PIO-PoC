# Stage 04C Case Selection

Origins were selected before state-array decode by ascending SHA-256 of `stage04c_origin_selection_v1 || lineage || variant || origin`, over legal origins 0–31.

| Lineage | Variant | Selected origins |
|---|---|---|
| LCDF_01 | VARIANT_LOW | 8, 19 |
| LCDF_01 | VARIANT_MAIN | 5, 24 |
| LCDF_04 | VARIANT_LOW | 4, 9 |
| LCDF_04 | VARIANT_MAIN | 4, 9 |
| LCDF_05 | VARIANT_LOW | 14, 13 |
| LCDF_05 | VARIANT_MAIN | 28, 23 |
| LCDF_06 | VARIANT_LOW | 31, 2 |
| LCDF_06 | VARIANT_MAIN | 20, 6 |
| LCDF_07 | VARIANT_LOW | 9, 25 |
| LCDF_07 | VARIANT_MAIN | 23, 7 |
| LCDF_08 | VARIANT_LOW | 0, 22 |
| LCDF_08 | VARIANT_MAIN | 6, 2 |

Each arm has 72 contexts: 6 lineages × 2 variants × 2 origins × 3 frozen model seeds. No origin, seed, lineage, or variant was replaced after observing results.
