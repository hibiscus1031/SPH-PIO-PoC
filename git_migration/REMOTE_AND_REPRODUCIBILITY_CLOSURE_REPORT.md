# Remote and reproducibility closure report

Audit date: 2026-08-12 (Asia/Shanghai)

## Executive status

- `PIO_UNTRACKED_AUDIT_PASS`
- `REPRODUCIBILITY_CLOSURE_PARTIAL`
- `PRIVATE_REMOTE_CLOSURE_IN_PROGRESS`

No source refactor, scientific recomputation, training, formal evaluation, frozen-data change, history rewrite, force operation, remote upload, or historical Stage reconstruction was performed.

## Repository and identity

| Item | Result |
|---|---|
| Local HEAD | `ecc529a6c248946c609089cdf8cfc8ef78eadfcf` on `main` |
| Closure commit | Pending final local commit |
| Global identity | `user.name` and `user.email` unset |
| Local identity | `hibiscus1031 <2623839613@qq.com>`; email is primary and verified by authenticated GitHub API |
| Historical HEAD identity | `谢槿博 <xiejinbo@Jinbo-Mac.local>`; not accepted for future publishing |
| Remote | None |
| Private visibility | Not applicable; repository was not created remotely |
| Tag | None; tag creation requires a successful first private push |

The identity resolution is recorded in `git_migration/git_identity_action_required.md`. The GitHub profile name is unset, so the authenticated account login is used as the repository-local author name; no email was inferred or guessed.

## PIO untracked resolution

`git_migration/pio_untracked_resolution.csv` records all 2,702 original non-ignored manual-review files with path, size, category, action, role, tracked equivalent, hash reference, and reason.

| Category | Count | Resolution |
|---|---:|---|
| `SHOULD_TRACK` | 31 | Secret-audited and staged for a future identity-reviewed commit |
| `HISTORICAL_EVIDENCE_ONLY` | 2,394 | Kept locally; authoritative tracked manifest hash retained |
| `SENSITIVE` | 135 | Kept under existing access controls; permissions not changed |
| `DUPLICATE` | 128 | Canonical tracked byte-identical copy recorded |
| `GENERATED_ARTIFACT` | 10 | Kept outside Git as derived/inspection output |
| `LITERATURE_REFERENCE` | 3 | Kept external; no redistribution claim |
| `EXTERNAL_DATA` | 1 | Kept external pending manifest/storage decision |
| `SHOULD_IGNORE` | 0 | None assigned by the conservative audit |
| `MANUAL_DECISION_REQUIRED` | 0 | None unresolved |

The 2,671 non-tracked decisions are applied as exact-path entries in this repository's local `.git/info/exclude`; no broad rule hides future files. The repository now has zero non-ignored untracked files. The local exclude file is not a scientific record; the versionable CSV is the authoritative resolution ledger.

## Security, size, and portability

The intended index contains 4,322 files and 219,110,947 apparent bytes.

- Secret/token/private-key signature audit: **PASS**, zero findings.
- Files over 100 MiB: **PASS**, zero.
- Files over 10 MiB: zero.
- Literature PDFs and cache paths: zero.
- Tracked numerical binaries: 106, all inherited from the pre-closure baseline; no new numerical binary or checkpoint was staged.
- Duplicate numerical SHA256 groups: 13, inherited from the pre-closure baseline and not rewritten because history rewriting is prohibited.
- Historical/report absolute-path occurrences: 24, retained without mechanical replacement.
- Executable/reusable portability issues: 4 occurrences, requiring future manual repair if those builders must run on another host:
  - `project_wide_synthesis/13_manifests/build_overlap_workbook.mjs:4`
  - `publication/verification_first_dynamic_neural_sph_v0_1/10_manifests/build_publication_p1_final.py:17`
  - `stage_02_Particle_Interaction_Operator/08_route_closure/manifests/build_stage02_research_record.py:25`
  - `stage_03_Dynamic_SPH_Transformer_Hybrid/08_route_closure/manifests/build_stage03_research_record.py:26`

These portability findings do not change frozen outputs and do not expose a secret, but they prevent a claim of host-independent execution for those scripts.

## External data and reproducibility

`DATA_RETRIEVAL_AND_INTEGRITY.md` identifies non-Git data classes, relative locations, authoritative manifests, integrity commands, completeness criteria, and publication boundaries. `scripts/verify_external_data.py` is read-only and supports `--manifest`, `--quick`, and `--full`.

Observed check: `project_final_evidence_freeze_manifest.json` quick verification passed for 15,090/15,090 entries with zero missing, size mismatch, hash mismatch, or unreadable entries. Full hashing of role-controlled material was not attempted because permissions must not be bypassed.

Overall reproducibility remains **PARTIAL**: code, reports, manifests, and selected definitions are versioned; the environment audit is partial; external payloads are local/institutional only; and historical Stage02–Stage08 code identity remains unknown.

## Remote and tag gate

GitHub CLI is authenticated as `hibiscus1031`, the verified identity is configured locally, and `hibiscus1031/SPH-PIO-PoC` was confirmed absent before creation. Remote creation remains gated on the final local commit and repeated pre-push audit. No alternative upload method is authorized.
