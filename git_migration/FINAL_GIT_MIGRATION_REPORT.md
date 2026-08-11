# 1 Executive status

**PRIVATE_REMOTE_CLOSURE_COMPLETE**

The pre-existing repository was preserved and extended by forward-only audited commits. No history was rewritten, no scientific artifact was deleted or regenerated, and no Stage02–Stage08 history was fabricated. The audited `main` branch is published only to a verified private GitHub repository.

# 2 Repository identity

| Field | Value |
|---|---|
| Path | `/Users/xiejinbo/Documents/SPH-PIO-PoC` |
| Repository name | `SPH-PIO-PoC` |
| Branch | `main` |
| Audited baseline commit | `a3b65ec6be41ceeedc15ace801773d39890d29eb` |
| Existing history retained | 81 pre-migration commits; baseline is commit 82 |
| Remote | `https://github.com/hibiscus1031/SPH-PIO-PoC.git` (`origin`) |
| Visibility | `PRIVATE`, verified through GitHub CLI |

# 3 What is tracked

The baseline contains 4,285 tracked files (213,874,227 apparent bytes; 204.0 MiB) before this report is added. The largest tracked file is the 7,692,330-byte Stage08Z evidence-freeze manifest; no tracked file exceeds 100 MiB.

Tracked content includes existing Stage00–Stage01 history, solver and metric code, 229 tests, later-stage Python/configuration sources, formal Markdown reports, small/deliberately selected CSV/JSON evidence, freeze/role/manifests, research records, publication source code, claim/evidence mappings, final CMAME exports, and the migration/provenance records.

The existing history already contained numerical artifacts (including NPZ files). They were not removed because doing so would require a prohibited history rewrite. The migration commit added no checkpoint or trajectory binary.

# 4 What is intentionally untracked

- 10,192 ignored files (1,862,599,128 bytes) cover bulk results, checkpoints/trajectories, training histories, caches, render trees, full-text literature, export archives, and role-controlled validation payloads.
- The former 2,702-file manual-review set is resolved in `git_migration/pio_untracked_resolution.csv`: 31 version-worthy files are committed and 2,671 exact local paths have explicit non-tracked dispositions plus local `.git/info/exclude` entries.
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

GitHub CLI is authenticated as `hibiscus1031`. The repository was confirmed absent, created with private visibility, and pushed through the ordinary non-force workflow:

```bash
gh repo create SPH-PIO-PoC --private --source=. --remote=origin
git push -u origin main
```

Do not use `--public`, force push, or overwrite an existing remote repository.

# 11 Remaining actions

No remaining action is required for the requested private-remote closure. Any future public release or external-data deposit requires a separate authorization and review.

# 12 Remote and reproducibility closure update

The 2,702-item manual-untracked audit is complete in `git_migration/pio_untracked_resolution.csv`: 31 small version-worthy scripts, manifests, definitions, registers, schedules, and preregistered plans passed a directed secret audit and are committed; the remaining 2,671 exact paths have explicit scientific dispositions and local-only `.git/info/exclude` entries. There are no unresolved `MANUAL_DECISION_REQUIRED` rows. Result: **PIO_UNTRACKED_AUDIT_PASS**.

External-data handling and the read-only manifest checker are documented in `DATA_RETRIEVAL_AND_INTEGRITY.md`. The project closure manifest passed quick existence/size checks for 15,090/15,090 entries. The intended index has zero secret signatures, zero files over 100 MiB, zero literature PDFs, and zero cache paths. The 106 numerical binaries and 13 duplicate numerical-hash groups are inherited tracked history; no new numerical binary was staged.

The publishing identity is resolved from authenticated GitHub account `hibiscus1031` and its primary verified email. No history was amended. `origin/main` was created and pushed privately without force; the annotated tag `repo-audited-2026-08-12` identifies the final closure-report state and carries the historical-state disclaimer. Current status: **REPRODUCIBILITY_CLOSURE_PARTIAL** and **PRIVATE_REMOTE_CLOSURE_COMPLETE**.
