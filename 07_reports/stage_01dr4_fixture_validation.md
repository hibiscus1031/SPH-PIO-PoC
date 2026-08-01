# Stage 01D-R4 Fixture Validation

四类夹具完全独立于 SPH 物理：A 验证长期 current 不误报，B 验证替换对象及时死亡，
C 验证故意 history leak 必须被检测，D 验证有界 two-generation pipeline 不误报。

| run | fixture | expected retention | current peak | old peak | same-slot peak | reclaimed | PASS |
|---|---|---|---|---|---|---|---|
| stage01dr4_fixture_a_r1 | A | False | 1 | 0 | 0 | True | True |
| stage01dr4_fixture_b_r1 | B | False | 0 | 0 | 0 | True | True |
| stage01dr4_fixture_c_r1 | C | True | 0 | 99 | 1 | True | True |
| stage01dr4_fixture_d_r1 | D | False | 0 | 0 | 0 | True | True |
| stage01dr4_fixture_a_r2 | A | False | 1 | 0 | 0 | True | True |
| stage01dr4_fixture_b_r2 | B | False | 0 | 0 | 0 | True | True |
| stage01dr4_fixture_c_r2 | C | True | 0 | 99 | 1 | True | True |
| stage01dr4_fixture_d_r2 | D | False | 0 | 0 | 0 | True | True |
| stage01dr4_fixture_a_r3 | A | False | 1 | 0 | 0 | True | True |
| stage01dr4_fixture_b_r3 | B | False | 0 | 0 | 0 | True | True |
| stage01dr4_fixture_c_r3 | C | True | 0 | 99 | 1 | True | True |
| stage01dr4_fixture_d_r3 | D | False | 0 | 0 | 0 | True | True |

12 个独立子进程全部按预登记正负标签分类。
