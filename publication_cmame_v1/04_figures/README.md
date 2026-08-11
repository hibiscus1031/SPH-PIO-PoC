# CMAME publication figure suite v1

This directory is a frozen-evidence publication package for the project state
`PROJECT_FULL_SOLVER_ROUTE_CLOSED_PUBLICATION_EVIDENCE_FROZEN`.

It contains:

- one graphical abstract;
- Figures 1–10;
- Supplementary Figures S1–S14;
- a shared CMAME/Elsevier style specification;
- per-figure source data, plot wrappers, captions, panel specifications, and evidence maps;
- aggregate evidence, claim-boundary, transformation, export, and visual-QC manifests.

SVG is the editable vector master, PDF is the vector submission alternative, and PNG
is the 600 dpi review/export derivative at 190 mm width. Continuous heatmaps and color
bars remain vector elements in SVG/PDF.

## Rebuild and audit

From the repository root:

```bash
python publication_cmame_v1/04_figures/00_style/build_main_figures.py
python publication_cmame_v1/04_figures/00_style/build_supplementary_figures.py
python publication_cmame_v1/04_figures/00_style/finalize_figure_suite.py
python publication_cmame_v1/04_figures/00_style/validate_figure_suite.py
```

The builders import no project solver, model, training, optimization, simulation, or
candidate-generation code. They read only registered public frozen evidence and apply
declared deterministic display transformations. Restricted artifacts are blocked and
are not figure sources.
