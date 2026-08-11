# Unified Stage06/07 formal training table

| campaign | arm | seed | terminal_update | selected_update | TRAIN_Q | validation_Q | seed_PASS | failure_gate | optimizer_steps | peak_RSS_bytes | checkpoint_integrity |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Stage06C | D1 | 20600611 | 1500 | 1500 | 0.9622027830868817 | 0.6421614364622288 | False | B_train_fit | 1500 | 898105344 | True |
| Stage06C | D1 | 20600612 | 1500 | 1500 | 0.9722365369659542 | 0.6542211423482678 | False | B_train_fit | 1500 | 807731200 | True |
| Stage06C | D1 | 20600613 | 1500 | 1500 | 0.968333653474331 | 0.6511944072520713 | False | B_train_fit | 1500 | 1001193472 | True |
| Stage06C | D2 | 20600611 | 1500 | 1500 | 0.9672182048887038 | 0.645522840749206 | False | B_train_fit | 1500 | 921403392 | True |
| Stage06C | D2 | 20600612 | 1500 | 1500 | 0.967138940636114 | 0.6399460132891721 | False | B_train_fit | 1500 | 904773632 | True |
| Stage06C | D2 | 20600613 | 1500 | 1500 | 0.9620084229649728 | 0.6411884808937747 | False | B_train_fit | 1500 | 973209600 | True |
| Stage06C | D3 | 20600611 | 800 | 500 | 0.7312509582353757 | 0.12346395777985979 | False | B_train_fit | 800 | 1262108672 | True |
| Stage06C | D3 | 20600612 | 820 | 520 | 0.7204726348914522 | 0.15666232982783143 | False | B_train_fit | 820 | 1209090048 | True |
| Stage06C | D3 | 20600613 | 1000 | 700 | 0.7246873353937681 | 0.07872118415663835 | False | B_train_fit | 1000 | 1229193216 | True |
| Stage07D | D1 | 20700711 | 1500 | 1500 | 0.9835541867711732 | 2.040410564270946 | False | B_train_fit,C_validation_transfer,D_HET_S2_02 | 1500 | 1152925696 | True |
| Stage07D | D1 | 20700712 | 1500 | 1500 | 0.9770863930292235 | 2.029706355648772 | False | B_train_fit,C_validation_transfer,D_HET_S2_02 | 1500 | 1113980928 | True |
| Stage07D | D1 | 20700713 | 1500 | 1500 | 0.9787099392218007 | 2.0349343964541005 | False | B_train_fit,C_validation_transfer,D_HET_S2_02 | 1500 | 1145487360 | True |
| Stage07D | D2 | 20700711 | 1500 | 1500 | 0.9769910864363911 | 2.031637650099132 | False | B_train_fit,C_validation_transfer,D_HET_S2_02 | 1500 | 1285783552 | True |
| Stage07D | D2 | 20700712 | 1500 | 1500 | 0.9799565645515831 | 2.035608899057209 | False | B_train_fit,C_validation_transfer,D_HET_S2_02 | 1500 | 1287094272 | True |
| Stage07D | D2 | 20700713 | 1500 | 1500 | 0.9798747737948718 | 2.0347537550674972 | False | B_train_fit,C_validation_transfer,D_HET_S2_02 | 1500 | 1437532160 | True |
| Stage07D | D3 | 20700711 | 1240 | 940 | 0.7956951652483188 | 1.762141387319439 | False | B_train_fit,C_validation_transfer,D_HET_S2_02 | 1240 | 1561772032 | True |
| Stage07D | D3 | 20700712 | 1380 | 1080 | 0.7919778295036133 | 1.759669732695545 | False | B_train_fit,C_validation_transfer,D_HET_S2_02 | 1380 | 1583497216 | True |
| Stage07D | D3 | 20700713 | 1240 | 940 | 0.7946715254893983 | 1.7642117892841283 | False | B_train_fit,C_validation_transfer,D_HET_S2_02 | 1240 | 1568866304 | True |

Stage06 and Stage07 normalized Q values are scale-contract-specific and must not be used as a scale-independent cross-stage performance comparison. Common-anchor comparisons use raw acceleration RMSE and relative zero-baseline reduction only.
