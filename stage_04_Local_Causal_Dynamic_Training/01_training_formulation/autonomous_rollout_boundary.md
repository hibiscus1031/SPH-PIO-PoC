# Autonomous-rollout boundary

Autonomous rollout begins when an accepted model prediction is committed and used as the current state for a subsequent solver step without replacement by the corresponding reference state. This is distinct from the formal Stage 04 v0.1 K=1 supervised transition.

Stage 04A authorizes no rollout. Stage 04E may train and evaluate only the preregistered K=1 task. Stage 04F may define autonomous rollout only after K=1 formal training and sealed evaluation and, if pursued, after independent K=2 gradient qualification and protocol registration.

Autonomous evaluation must separately assess numerical safety, state error growth, conservation/equivariance, topology-event behavior, and stability over preregistered horizons. Its thresholds and failure handling cannot be derived from released sealed-test or D-R3 outcomes. Divergence, nonfinite state, graph failure, or stability failure must be retained rather than censored.

A low K=1 or K=2 state loss does not imply stable autonomous behavior because distribution shift, accumulated integration error, state-dependent graph changes, and recurrent-history drift are absent or limited under local supervision. Therefore the claim `training success` is always narrower than `complete solver success`.

Full-solver claims require, at minimum, successful autonomous rollout plus independent D-R3 validation and refinement evidence in Stage 04G. Stage 04A makes none of these claims.
