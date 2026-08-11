# External data retrieval and integrity

This repository intentionally does not place every scientific artifact in ordinary Git. No data were uploaded or relocated during this closure.

## External material and local locations

| Material | Local repository-relative locations | Why external |
|---|---|---|
| Bulk numerical results and records | Stage directories under `**/results/`, `**/outputs/`, `**/records/`, `**/trajectories/`, and related stage-specific stores | High-volume generated evidence is unsuitable for ordinary Git. |
| Checkpoints and training histories | Stage05–Stage07 checkpoint, optimizer, training-history, validation-history, and checkpoint-dynamics directories | Large binary/stateful artifacts are preserved locally and identified by formal manifests. |
| Numerical arrays and model payloads | `*.npy`, `*.npz`, `*.pt`, `*.pth`, `*.ckpt`, `*.h5`, `*.hdf5` outside the deliberately retained historical Git set | Ordinary Git is not the artifact store; existing historical binaries were not rewritten out of history. |
| Render/cache/export working trees | render, preview, font cache, archive, and inspection directories | Rebuildable or packaging output rather than scientific source. |
| Literature full text | literature/full-text caches and reference PDFs | Reference material may be copyright-restricted and is not project source. |
| Role-controlled evidence | Stage04 sealed/private validation and Stage08 private-design locations | Access and scientific-role controls must be preserved; permissions must not be bypassed merely to hash or publish them. |
| Manual-review artifacts | Paths enumerated in `git_migration/pio_untracked_resolution.csv` | Each file has an explicit category, role, recommended action, duplicate link, or hash reference. |

## Authoritative manifests

- `stage_08Z_Project_Closure_Publication/00_freeze/project_final_evidence_freeze_manifest.json` is the broad project-closure inventory. It records relative paths, byte sizes, SHA256 values, readability state, and scientific roles for 15,090 artifacts.
- Stage-specific manifests remain authoritative for their own experiments, checkpoints, trajectories, role assignments, and frozen inputs.
- `provenance/datasets/dataset_manifest.csv` is a Git-side index of existing manifests. It does not replace them and is not a data-download catalogue.
- `git_migration/pio_untracked_resolution.csv` links non-ignored local artifacts to tracked equivalents or existing manifest hashes where available.

There is no authenticated public data repository, DOI, accession, or approved external download URL in the audited repository. Therefore “retrieval” currently means restoring the original repository-relative tree from an authorized local/institutional backup, then validating it against the manifests. A clone alone is not a complete data package.

## Read-only verification

The checker reads manifests and payloads only. It does not generate, repair, rename, or change any artifact.

```bash
cd /Users/xiejinbo/Documents/SPH-PIO-PoC
python scripts/verify_external_data.py \
  --manifest stage_08Z_Project_Closure_Publication/00_freeze/project_final_evidence_freeze_manifest.json \
  --quick
```

Quick mode checks existence and every recorded byte size. Full mode additionally computes SHA256 and may take substantial time:

```bash
python scripts/verify_external_data.py \
  --manifest stage_08Z_Project_Closure_Publication/00_freeze/project_final_evidence_freeze_manifest.json \
  --full
```

A complete authorized tree has zero `MISSING`, `SIZE_MISMATCH`, `HASH_MISMATCH`, and `UNREADABLE` results. Full verification of sealed/private material must be performed only by an authorized user under the existing access policy; do not change permissions to make the audit pass.

Observed quick-check snapshot on 2026-08-12: 15,090/15,090 entries verified; zero missing, size mismatch, hash mismatch, or unreadable entries. This is an existence/size result, not a full-project hash claim.

## Publication boundary

- Potentially publishable after a separate license, authorship, privacy, and intellectual-property review: repository source, human-authored documentation, non-sensitive manifest metadata, and explicitly approved synthetic summaries.
- Not currently authorized for public release: sealed/private or role-controlled evidence, credentials/local configuration, checkpoints, bulk trajectories/training histories, and third-party literature PDFs.
- Publication decision not yet made: all other external numerical data and generated evidence. Their synthetic origin does not itself grant release authorization.

Until that review and a sanctioned repository location exist, all external data have status `LOCAL_OR_INSTITUTIONAL_STORAGE_ONLY`; this document does not authorize upload to any service.
