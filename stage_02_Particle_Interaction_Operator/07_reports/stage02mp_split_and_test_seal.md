# Stage 02M-P — Split and test seal

恰有 4 个 lineage components：train BLIND_FAMILY_01/02、validation V02_BLIND_VALIDATION_01、test V02_BLIND_TEST_01。Split 10/5/5，cross-split lineage=0；未采用 particle/edge/patch 或 resolution/support伪独立 split。

新 test seal 的 loader/direct-path/wildcard/metric-evaluator denial全部通过；test_target_access=false，test target decode=0，且未生成 test_release_manifest。BLIND_FAMILY_03/04 不进入新 collection，继续分别是 consumed historical validation/test only。
