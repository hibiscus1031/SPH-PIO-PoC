# Stage 01G-E dependency audit

Static AST inspection and the frozen dependency graph cover all nine evaluator Python files.

The graph contains only internal evaluator edges and Python standard-library dependencies: `collections.abc`, `copy`, `hashlib`, `json`, `math`, `pathlib`, and `typing`. There are no external runtime packages.

Confirmed absent imports and call targets:

- solver and `01_solver` modules;
- RK2 modules or call targets;
- DOP853 or SciPy integrators;
- source adapters, manufactured-solution or MMS modules;
- Stage 01F5B evaluator code;
- training or learned-corrector modules.

The evaluator modules do not import `torch`, NumPy, YAML, subprocess, filesystem writers, or networking. Provenance reads explicitly supplied frozen files; metric functions operate on caller-supplied ordinary Python mappings and sequences.

Dependency audit: **PASS**.
