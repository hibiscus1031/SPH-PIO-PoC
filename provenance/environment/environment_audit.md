# Environment audit

## Existing dependency sources

- `00_environment/environment_from_history.yml`
- `00_environment/environment_full.yml`
- `00_environment/pip_freeze.txt`

## Assessment

`00_environment/environment_from_history.yml` and `00_environment/environment_full.yml` are existing evidence sources. They were not regenerated or upgraded.
The project lacks a verified cross-platform lockfile; reproducibility is therefore **PARTIAL**.
No system-wide `pip freeze` was captured, because that would conflate unrelated host packages with project dependencies.
