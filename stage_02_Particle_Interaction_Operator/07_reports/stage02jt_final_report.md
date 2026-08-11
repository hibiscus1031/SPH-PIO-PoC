# Stage 02J-T Final Report

## Final status

**REGULARITY_GATE_V03_NOT_QUALIFIED**

Stage 02J-U authorization is **false**.

## 1–5. Historical preservation, decomposition, closure, semantics, and single candidate

Stage 02J-S remains `VERSIONED_MULTIFAMILY_DATASET_NOT_READY`; its negative-control failure and closed held-out gate are unchanged. The v0.1 candidate state remains diagnostic/nonmaterialized, v0.2 qualified candidates remain zero, and Stage 02K remains unauthorized.

The algebraic decomposition was evaluated without redefining `S_h`. All ten development cases satisfy `S_h^2=M_h^2+D_h^2`; the maximum absolute closure error is `1.665e-16`. The Stage 02J-S sign-flip mechanism is **SIGNFLIP_FALSE_POSITIVE_MIXED** under the preregistered semantic rule: 10/14 historical false positives were magnitude-significant, 1/14 direction-significant, and all particlewise magnitude-position mappings were preserved.

Only `attribution_contract_v0_3 = magnitude_direction_conjunction` was preregistered. No candidate sweep or post-result choice was used.

## 6–9. Calibration, Clopper–Pearson, structured targets, and invariance

All 30 development case/control combinations passed the 512-realization, one-sided 95% Clopper–Pearson gate. The maximum upper bound was `0.025525872900`.

| Development resolution case | M_h | D_h | p_mag | p_dir | Joint |
|---|---:|---:|---:|---:|---|
| crossmode_a_n12_h26 | 0.399753799232 | 0.748028866276 | 0.778210116732 | 0.003891050584 | FAIL |
| crossmode_a_n16_h26 | 0.414112673574 | 0.528011124480 | 0.003891050584 | 0.003891050584 | PASS |
| crossmode_a_n20_h26 | 0.386366690842 | 0.393579980769 | 0.003891050584 | 0.003891050584 | PASS |
| i_anchor_n16_h26_regular | 0.256990012269 | 0.422160883627 | 0.003891050584 | 0.003891050584 | PASS |
| i_res_n12_h26_regular | 0.303451905228 | 0.566401452466 | 0.003891050584 | 0.003891050584 | PASS |
| i_res_n20_h26_regular | 0.218287407922 | 0.335381280908 | 0.003891050584 | 0.003891050584 | PASS |

PV_EXISTING passed 3/3. CROSSMODE_A failed because N12 has `p_mag=0.778210116732`, although `p_dir=1/257` and all refinement/non-null gates passed. This single required structured-gate failure prevents v0.3 qualification. All 80 requested M/D/p invariance checks passed.

## 10–17. Contract hash, blind freeze, formulas, reference, conservation, transfer, and non-blind boundary

- Final `regularity_contract_v0_3.yaml` hash: **NOT GENERATED**.
- Prospective candidate hash: `sha256:82ab8eaef0efef6dc67234a5d93cd8a2be427755730a7bfffc713e4897592e6a`.
- Blind generator source/freeze hashes were recorded before development execution.
- Four preregistered blind identities and seeds were retained, but concrete formulas were not materialized.
- Positivity/Mach, blind references, uncertainties, conservation, and regularity were not evaluated because the contract hash gate never opened.
- No blind family was replaced.
- DIAGONAL_B/MIXED_C remained historical non-blind evidence and contributed nothing to qualification.

## 18–22. Authorization, prohibited work, and integrity

- Stage 02J-U authorized: **false**.
- Dataset records materialized: **no**.
- Split or normalization performed: **no**.
- Model, Transformer, attention, or neural network implemented: **no**.
- Training or optimizer executed: **no**.
- Performance claim produced: **no**.
- Historical files unchanged: 294/294; mismatches: 0.
- Stage 01 modified: **no**.

No threshold, target, formula, family role, or verdict was changed to make a candidate pass.
