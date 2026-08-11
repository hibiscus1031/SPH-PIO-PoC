# Stage07C formal retraining protocol

Formal seeds: [20700711, 20700712, 20700713]. AdamW `(0.9,0.999)`, eps `1e-12`, weight decay `0`, AMSGrad false, clip `1.0`, sole LR `1e-5`. Budget 320--1500 updates; 40-update linear warmup then cosine to `1e-6`; validation/checkpoint interval 20; early stopping patience 300 with `1e-5` global-Q improvement.
