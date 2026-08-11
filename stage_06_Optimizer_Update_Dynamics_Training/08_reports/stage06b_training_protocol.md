# Stage 06B Formal Training Protocol

Protocol hash: `sha256:b7918bde82b104895b6d47c798801608938c661c3f8b249f4c832c98c3a83cbe`. Nine fresh CPU/float64/MATH runs use seeds 20600611–20600613, AdamW betas (0.9,0.999), eps 1e-12, weight decay 0, AMSGrad false, global gradient clipping 1.0, and LR 1e-5. Budget is 1500 updates (minimum 320); 40-update linear warmup 0.1×→1× then cosine to 0.1× at update 1500. Values below 1e-5 are marked schedule-only `subqualification_decay_only`. Loss and TRAIN scale remain frozen.
