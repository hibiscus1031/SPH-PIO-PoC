# Stage 02J Dataset Schema

## Schema composition

Each Stage 02J record contains an unmodified `stage02b_record` that passes the frozen `pio_dataset_schema.json`, plus Stage 02J extensions validated by `stage02j_graph_record_schema.json`. This composition preserves the Stage 02B contract while adding fields needed for dual-reference audit, nodal-force supervision, reciprocal-edge mapping, canonical provenance, and pair-only scope qualification.

The Stage 02B record contains particle state, neighbor information, `a_SPH`, primary `a_ref`, `delta_a`, metadata, six-bucket uncertainty, provenance, and a pending diagnostic eligibility entry. The Stage 02J extension contains:

- identity and provenance: dataset/case/family/state/resolution/support/disorder/reference identities and source/config/state/graph hashes;
- reciprocal graph extensions: reciprocal edge index, active-kernel flag, zero-weight exterior flag, and total/active neighbor counts;
- `a_FOURIER2`, `a_ANALYTIC`, and their difference;
- `delta_a`, mass, and nodal force `y=m*delta_a`;
- source-target, 6/6 attribution, pair-force compatibility, and architecture-scope qualification.

All vector accelerations use `m s^-2`, mass uses `kg`, and nodal force uses `kg m s^-2`. The sign is frozen as `a_reference_minus_a_sph`.

## Node-level supervision contract

Formal supervision is node-level:

\[
\Delta a_i=a_{FOURIER2,i}-a_{SPH,i},\qquad y_i=m_i\Delta a_i.
\]

Every record verifies both identities. `edge_pair_force_target_saved=false` and `least_squares_projection_saved_as_label=false`.

## Edge-label non-uniqueness boundary

An incidence representation `Bf=y` has a non-trivial null space, so an antisymmetric pair decomposition is not a unique physical edge label. The Stage 02I-R least-squares projection remains audit evidence only. It is absent from dataset labels, ground truth, and supervision.

## Feature permission

`feature_permission_table.yaml` classifies fields as `feature_allowed`, `feature_forbidden`, or `audit_only`. Allowed future inputs are limited to baseline state and legal graph quantities. References, target values, nodal force, target-derived statistics, split identity, and verdicts are forbidden as model inputs. Particle/edge IDs and file order are audit-only. `a_SPH` is conservatively audit-only in version 0.1 pending a separate architecture decision.

The primary reference is represented as Stage 02B `R1_continuum_compatible`, with compatibility explicitly limited to the frozen spatial operator scope. This does not confirm the full PDE model form or the viscosity operator form.

## Uncertainty ledger

Each record preserves six separate buckets: reference, temporal, spatial, model-form, topology, and resource. Fourier/analytic field difference supplies reference uncertainty; same-state/no-time-derivative makes temporal error not applicable; spatial attribution, topology, and resources point to frozen evidence. `GCI not justified` and `single_total_gci_permitted=false` remain unchanged.

