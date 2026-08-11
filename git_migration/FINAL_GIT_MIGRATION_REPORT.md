# 1 Executive status

**GIT_MIGRATION_COMPLETE_LOCAL_ONLY**

The pre-existing repository was preserved and extended by one forward-only audited baseline commit. No history was rewritten, no scientific artifact was deleted or regenerated, and no Stage02–Stage08 history was fabricated. The repository remains local because GitHub CLI is not installed.

# 2 Repository identity

| Field | Value |
|---|---|
| Path | `/Users/xiejinbo/Documents/SPH-PIO-PoC` |
| Repository name | `SPH-PIO-PoC` |
| Branch | `main` |
| Audited baseline commit | `a3b65ec6be41ceeedc15ace801773d39890d29eb` |
| Existing history retained | 81 pre-migration commits; baseline is commit 82 |
| Remote | none |
| Visibility | LOCAL ONLY / NOT PUBLISHED |

# 3 What is tracked

The baseline contains 4,285 tracked files (213,874,227 apparent bytes; 204.0 MiB) before this report is added. The largest tracked file is the 7,692,330-byte Stage08Z evidence-freeze manifest; no tracked file exceeds 100 MiB.

Tracked content includes existing Stage00–Stage01 history, solver and metric code, 229 tests, later-stage Python/configuration sources, formal Markdown reports, small/deliberately selected CSV/JSON evidence, freeze/role/manifests, research records, publication source code, claim/evidence mappings, final CMAME exports, and the migration/provenance records.

The existing history already contained numerical artifacts (including NPZ files). They were not removed because doing so would require a prohibited history rewrite. The migration commit added no checkpoint or trajectory binary.

# 4 What is intentionally untracked

- 10,192 ignored files (1,862,599,128 bytes) cover bulk results, checkpoints/trajectories, training histories, caches, render trees, full-text literature, export archives, and role-controlled validation payloads.
- 2,702 additional files (158,633,853 bytes) remain visible for deliberate manual review; they are primarily generated JSON evidence and module-local figure duplicates. Their exact paths and reasons are frozen in `audit/intentionally_untracked_inventory.csv`.
- The unreadable Stage04 `validation_private` directory and Stage08 `private_design` payload are retained on disk without permission changes. Only their access/role/seal metadata is tracked.

Untracked does not mean deleted; every source artifact remains in its original location.

# 5 Git LFS

- Installed: **NO**
- Used: **NO**
- LFS patterns: none
- LFS volume: 0 bytes

The audited tracked set has no file above 7.7 MiB, so installing LFS was not required for this baseline. Large checkpoints, trajectories, literature PDFs, and export archives remain external. A selective future LFS policy is recorded in `audit/git_lfs_policy.md`.

# 6 Provenance

- Repository state: `provenance/repository_state.md`
- Existing manifest/hash index: `provenance/datasets/dataset_manifest.csv`
- Experiment registry: `provenance/experiments/experiment_registry.csv`
- Environment audit: `provenance/environment/environment_audit.md`
- Historical stage audit: `audit/historical_code_provenance_audit.csv`
- Exact baseline candidate paths: `audit/baseline_candidate_paths.txt`

The dataset index hashes existing manifest files but does not replace their scientific authority or copy large data into Git.

# 7 Historical limitations

Stage00 has one and Stage01 has 79 subject-matched authentic Git commits, with existing tags retained. Stage02–Stage08 have freeze manifests, evidence hashes, reports, and current source files, but no independently verified historical Git source snapshots. Therefore no historical Stage02–Stage08 commits or tags were created. Their experiment registry status is `UNKNOWN_HISTORICAL_CODE_STATE`; the migration baseline must not be cited as their experiment-time code.

# 8 Secret audit

**PASS.** The bounded filename and content-signature audit found no private-key, AWS, GitHub, Hugging Face, OpenAI, or explicit credential signature in the tracked candidate set. Secret values were never printed. Role-controlled scientific payloads were excluded separately from credential risk.

# 9 Reproducibility status

| Area | Status | Basis |
|---|---|---|
| Code | PARTIAL | Core/later-stage sources and tests are versioned; historical Stage02–08 code-to-run identity is not proven. |
| Data | PARTIAL | Extensive frozen manifests/hashes exist; bulk payloads remain local/external. |
| Figures | PARTIAL | Figure sources and final selected exports are tracked; some large source data are external. |
| Tables | PARTIAL | Source packs/mappings exist; not every table has a verified end-to-end generator. |
| Environment | PARTIAL | Existing environment YAML evidence is retained; no verified cross-platform lockfile. |

Validation: 377 tests collected; a bounded non-training subset passed 5/5. No training, trajectory, sealed test, or artifact regeneration was run.

# 10 GitHub status

Local only. `gh` was not installed and no remote was created. After setting a deliberate Git author identity, installing/authenticating GitHub CLI, and repeating the secret/large-file audit, the intended private-only command is:

```bash
gh repo create SPH-PIO-PoC --private --source=. --remote=origin
git push -u origin main
```

Do not use `--public`, force push, or overwrite an existing remote repository.

# 11 Remaining actions

1. Configure and verify `user.name` and `user.email`; the baseline used Git's host-derived identity `谢槿博 <xiejinbo@Jinbo-Mac.local>`.
2. Review the 2,702-item manual-untracked ledger and promote only genuinely version-worthy small evidence in ordinary forward commits.
3. Establish a reviewed dependency/lock strategy without replacing the historical environment evidence.
4. Define external object/data storage and retrieval instructions for frozen datasets/checkpoints.
5. Create a private GitHub remote only after authentication and pre-push re-audit.
