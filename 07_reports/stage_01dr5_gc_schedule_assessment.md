# Stage 01D-R5 GC-schedule Assessment

| run | mode | max retired | max bytes | same-slot | max gen/slot | first peak | second peak | slope | R² | natural GC | post-GC max | periodic zero | GC wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stage01dr5_g1_r1 | G1 | 69 | 34865152 | 13 | 10 | 57 | 69 | 0.01066 | 0.233 | 581 | 67 | 0.025 | 0.000 |
| stage01dr5_g2_r1 | G2 | 19993 | 10712432640 | 13 | 1999 | 9993 | 19993 | 10 | 1.000 | 0 | -1 | 0.000 | 0.000 |
| stage01dr5_g3_r1 | G3 | 33 | 18710528 | 13 | 6 | 33 | 25 | -0.0004273 | 0.001 | 720 | 25 | 1.000 | 1.888 |
| stage01dr5_g1_r2 | G1 | 64 | 34766848 | 13 | 9 | 61 | 64 | 0.005811 | 0.075 | 579 | 54 | 0.025 | 0.000 |
| stage01dr5_g2_r2 | G2 | 19993 | 10712432640 | 13 | 1999 | 9993 | 19993 | 10 | 1.000 | 0 | -1 | 0.000 | 0.000 |
| stage01dr5_g3_r2 | G3 | 33 | 18710528 | 13 | 6 | 33 | 25 | -0.000601 | 0.003 | 720 | 25 | 1.000 | 1.892 |
| stage01dr5_g1_r3 | G1 | 66 | 37388288 | 13 | 10 | 62 | 66 | 0.007448 | 0.121 | 579 | 66 | 0.013 | 0.000 |
| stage01dr5_g2_r3 | G2 | 19993 | 10712432640 | 13 | 1999 | 9993 | 19993 | 10 | 1.000 | 0 | -1 | 0.000 | 0.000 |
| stage01dr5_g3_r3 | G3 | 33 | 18710528 | 13 | 6 | 33 | 25 | -0.0004456 | 0.002 | 720 | 25 | 1.000 | 1.894 |

G1 的 retired-count 总归零观测如下；这一区分“自然 GC 事件发生”与“所有 retired
storage 同时归零”，不把任一次 generation-0 collection 误写成全量归零：

| run | zero observations | first zero step | last zero step | second-half zeros |
|---|---|---|---|---|
| stage01dr5_g1_r1 | 22 | 1 | 219 | 0 |
| stage01dr5_g1_r2 | 10 | 1 | 1400 | 3 |
| stage01dr5_g1_r3 | 15 | 1 | 1438 | 8 |

default GC bounded=`True`；GC-disabled linear growth=
`True`；periodic checkpoint zero=
`True`。三次 G1 均有重复总归零观测且预登记的前/后半程
峰值判据通过；但 r1 的最后一次总归零在 step 219，不能声称三次运行在整个 2000 步内都
持续总归零。G3 的 wall-time 只作为诊断开销，周期 collect 没有被采用为正式修复。
