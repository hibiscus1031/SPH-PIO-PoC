# SPH-PIO-PoC

Verification-first proof of concept for structure-preserving particle-interaction operators and conservative neural corrections in smoothed particle hydrodynamics (SPH).

## Scientific scope and status

The repository contains SPH verification and validation, manufactured-solution studies, conservative pair-force operators, defect-target and representability analyses, gradient/optimizer-path verification, formal training campaigns, qualification gates, support-gap diagnosis, and publication-source material.

The frozen project conclusion is **not** a successful trained SPH-Transformer solver. Stage08Z records `PROJECT_FULL_SOLVER_ROUTE_CLOSED_PUBLICATION_EVIDENCE_FROZEN`: the tested in-project full-solver training-development route is closed, the fresh-validation closure is 0/4, autonomous rollout remains unqualified, and the sealed test remains closed. The authorized publication route is a verification-first, qualification-first, failure-driven computational methodology article. This is a route-specific result, not a general impossibility claim.

## Repository structure

- `00_environment/`–`07_reports/`: original environment, solver, experiment, metric, and report structure.
- `stage_02_*`–`stage_08*`: later scientific stages captured at the audited migration baseline.
- `tests/`: verification and regression tests.
- `publication/` and `publication_cmame_v1/`: manuscript, claim/evidence, and figure-generation sources.
- `provenance/`: repository, environment, dataset-manifest, experiment, and release provenance.
- `git_migration/`: migration inventory, secret/large-file audit, and policy records.

## Installation

Historical environment evidence is retained in `00_environment/environment_from_history.yml` and `00_environment/environment_full.yml`. These files were not regenerated or upgraded during Git migration. Review `provenance/environment/environment_audit.md` before creating an isolated environment; the current repository does not claim a fully locked cross-platform environment.

## Reproducibility and data policy

Large datasets, trajectories, checkpoints, training histories, caches, and literature full text remain on disk outside ordinary Git. Existing freeze manifests and SHA-256 records remain the scientific sources of truth; `provenance/datasets/dataset_manifest.csv` is only an index to them. Experiment-to-code links that cannot be proven are marked `UNKNOWN_HISTORICAL_CODE_STATE`.

Figure and table regeneration status is documented in `publication/REPRODUCIBILITY.md`. Do not run training, sealed-test evaluation, or frozen-data generation as part of routine repository validation.

## Qualification philosophy

Claims are bounded by preregistered gates, conservation and differentiability checks, source/role separation, held-out evidence, and explicit failure attribution. Passing a numerical or implementation check does not authorize predictive-performance or generalization claims that are not recorded in the frozen claim boundary.

## License and citation

No license has been selected. Until the owner adds one, all rights remain reserved. A formal citation record is pending publication; do not infer a DOI or bibliographic claim from this repository.
