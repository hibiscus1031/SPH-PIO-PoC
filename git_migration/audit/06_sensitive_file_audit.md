# Sensitive-file audit

No secret values are reproduced in this report.

Status: **PASS**

No private-key, AWS, GitHub, Hugging Face, OpenAI, or credential-risk file signature was detected by the bounded pre-commit scan.
This is a migration safety scan, not a guarantee against every possible secret format.

## Role-controlled scientific payloads

| Path | Risk type |
|---|---|
| `stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b/access_control/validation_private/` | ROLE-CONTROLLED / unreadable during migration; excluded without permission changes |
| `stage_08_Systematic_Coverage_V3/01_systematic_coverage_design/validation_candidate_bank/private_design/` | BLIND-VALIDATION DESIGN PAYLOAD; excluded while role/seal manifests remain tracked |
