# Git LFS policy

Git LFS availability: **git: 'lfs' is not a git command. See 'git --help'.**

No LFS rules are activated because Git LFS is not installed. No installation was attempted.

| Pattern | Count | Total MiB | Recommendation | Reason |
|---|---:|---:|---|---|
| `*.pdf` | 105 | 157.62 | SELECTIVE_LFS_AFTER_INSTALL | only final, necessary large publication binaries merit LFS |
| `*.png` | 769 | 233.42 | SELECTIVE_LFS_AFTER_INSTALL | only final, necessary large publication binaries merit LFS |
| `*.jpg` | 0 | 0.00 | ORDINARY_GIT_IF_FINAL | small final artifacts remain manageable and reviewable |
| `*.jpeg` | 0 | 0.00 | ORDINARY_GIT_IF_FINAL | small final artifacts remain manageable and reviewable |
| `*.tiff` | 0 | 0.00 | ORDINARY_GIT_IF_FINAL | small final artifacts remain manageable and reviewable |
| `*.docx` | 8 | 1.17 | ORDINARY_GIT_IF_FINAL | small final artifacts remain manageable and reviewable |
| `*.pptx` | 0 | 0.00 | ORDINARY_GIT_IF_FINAL | small final artifacts remain manageable and reviewable |
| `*.xlsx` | 2 | 0.02 | ORDINARY_GIT_IF_FINAL | small final artifacts remain manageable and reviewable |
| `*.pt` | 1882 | 637.37 | EXTERNAL_NOT_LFS | dataset/checkpoint payloads default to external storage with manifest references |
| `*.pth` | 0 | 0.00 | EXTERNAL_NOT_LFS | dataset/checkpoint payloads default to external storage with manifest references |
| `*.ckpt` | 0 | 0.00 | EXTERNAL_NOT_LFS | dataset/checkpoint payloads default to external storage with manifest references |
| `*.npz` | 4364 | 213.21 | EXTERNAL_NOT_LFS | dataset/checkpoint payloads default to external storage with manifest references |
| `*.h5` | 0 | 0.00 | EXTERNAL_NOT_LFS | dataset/checkpoint payloads default to external storage with manifest references |
| `*.hdf5` | 0 | 0.00 | EXTERNAL_NOT_LFS | dataset/checkpoint payloads default to external storage with manifest references |
