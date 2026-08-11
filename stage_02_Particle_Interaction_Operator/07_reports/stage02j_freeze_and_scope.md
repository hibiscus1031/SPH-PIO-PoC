# Stage 02J Freeze and Scope

## Limited authorization

Stage 02J uses only the Stage 02I-R `PAIR_ONLY_REGULAR_SCOPE` decision. The authorized source records are:

1. `i_res_n12_h26_regular`
2. `i_anchor_n16_h26_regular`
3. `i_res_n20_h26_regular`
4. `i_sup_n16_h22_regular`
5. `i_sup_n16_h30_regular`

The authorization is prospective and limited; it does not overwrite the historical Stage 02I `Stage02J_authorized=false` record.

## Input freeze

`stage02j_input_freeze_manifest.json` freezes 16 logical evidence roles. The split and leakage roles intentionally resolve to the same Stage 02B `split_strategy.md`, because leakage rules are embedded in that frozen contract rather than stored in a separate file. The manifest includes:

- Stage 02I-R final, architecture, qualification, and target-hash evidence;
- Stage 02I final report, case matrix, seven target records, attribution, conservation, and historical eligibility;
- Fourier/analytic comparison evidence;
- Stage 02B schema, eligibility, split/leakage, and uncertainty contracts.

The five authorized regular record hashes and two jitter record hashes match the prior Stage 02I-R SHA-256 freeze. All inputs were reverified before materialization.

## Sample and target boundary

The sample unit is one complete particle graph. The corpus contains exactly five samples; particles, edges, vector components, and local patches are not IID samples. No repetition, slicing, copying, random particle sampling, frame expansion, or augmentation was used.

Only existing Stage 02I targets were materialized. No target, physical state family, trajectory, or temporal frame was generated. Historical files were read-only.

## Jitter boundary

`i_dis_n16_h26_jitter05` and `i_dis_n16_h26_jitter10` remain `distribution_shift_diagnostic_only`. They have no training label permission, normalization-fit permission, pair-force supervision permission, or split membership.

