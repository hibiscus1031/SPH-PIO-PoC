# Teacher-forcing boundary

`history_warm_start` and teacher forcing are distinct. The former supplies at most the three accepted reference states strictly before the rollout origin so a length-four causal model can start. It is permitted only with explicit provenance and is identical across arms where applicable.

After the rollout origin, `teacher_forcing_after_start=false` for training and evaluation. Each next start state and committed history token derives from the arm's own previous accepted prediction. Inserting, blending, resetting to, or recomputing from a reference state inside the segment is prohibited.

Any curriculum or diagnostic teacher-forced path would require a separately named, preregistered non-formal protocol and cannot count as D4/D5 evidence. Formal reports must disclose warm-start length and self-feed status.
