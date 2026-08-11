# Stage 06 C Validation and Selection

| Run | Terminal | Updates | Selected | TRAIN Q | VALIDATION Q | LCDF_02 | LCDF_09 | Seed PASS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D1_seed20600611 | MAX_UPDATES | 1500 | 1500 | 0.962202783 | 0.642161436 | 0.609685030 | 0.673072645 | False |
| D1_seed20600612 | MAX_UPDATES | 1500 | 1500 | 0.972236537 | 0.654221142 | 0.629086640 | 0.678425092 | False |
| D1_seed20600613 | MAX_UPDATES | 1500 | 1500 | 0.968333653 | 0.651194407 | 0.624959481 | 0.676412566 | False |
| D2_seed20600611 | MAX_UPDATES | 1500 | 1500 | 0.967218205 | 0.645522841 | 0.622172276 | 0.668057733 | False |
| D2_seed20600612 | MAX_UPDATES | 1500 | 1500 | 0.967138941 | 0.639946013 | 0.626496102 | 0.653119005 | False |
| D2_seed20600613 | MAX_UPDATES | 1500 | 1500 | 0.962008423 | 0.641188481 | 0.616365276 | 0.665085846 | False |
| D3_seed20600611 | EARLY_STOPPED | 800 | 500 | 0.731250958 | 0.123463958 | 0.139288423 | 0.105287383 | False |
| D3_seed20600612 | EARLY_STOPPED | 820 | 520 | 0.720472635 | 0.156662330 | 0.189006962 | 0.115596452 | False |
| D3_seed20600613 | EARLY_STOPPED | 1000 | 700 | 0.724687335 | 0.078721184 | 0.081694681 | 0.075630872 | False |

Selection used only the minimum VALIDATION global-balanced Q_def at update >=320, with earlier-update tie break. The frozen zero-correction VALIDATION baseline is 0.686177095; baseline deltas are diagnostic only.
