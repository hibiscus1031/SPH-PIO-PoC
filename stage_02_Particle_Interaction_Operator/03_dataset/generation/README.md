# Stage 02C Audit-Scale Generation Pipeline

Pipeline order is frozen as:

```text
configuration
  -> SPH state generation
  -> R2 reference evaluation
  -> delta_a computation
  -> eligibility engine
  -> sample storage
```

Run from the repository root with:

```bash
python3 stage_02_Particle_Interaction_Operator/03_dataset/generation/generate_audit_dataset.py
python3 stage_02_Particle_Interaction_Operator/03_dataset/audits/audit_dataset.py
```

The generator enumerates every case already frozen in `../cases/case_manifest.yaml`; it does not randomly generate and
then select cases. It writes only R2 audit records. The topology negative control is predeclared and retained to exercise the
automatic `rejected` path. R2 positive records remain `diagnostic` under the Stage 02B policy and are not training data.

This pipeline contains no model, Transformer, attention, optimizer, training, split assignment, normalization statistics,
validation, or performance evaluation.
