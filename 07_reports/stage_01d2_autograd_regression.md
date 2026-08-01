# Stage 01D2 autograd regression

| parameter | steps | autograd_gradient | finite_difference_gradient | relative_difference | finite | nonzero | status |
|---|---|---|---|---|---|---|---|
| initial_velocity_amplitude | 1 | 0.4999630965993064 | 0.49996309657573956 | 4.713710937131066e-11 | True | True | PASS |
| initial_velocity_amplitude | 16 | 0.49940977176705476 | 0.4994097717453405 | 4.34798090536929e-11 | True | True | PASS |
| initial_velocity_amplitude | 3 | 0.49988929733631693 | 0.4998892973312463 | 1.0143467013770841e-11 | True | True | PASS |
| initial_velocity_amplitude | 5 | 0.4998155076627141 | 0.4998155076485489 | 2.8340906457926268e-11 | True | True | PASS |
| initial_velocity_amplitude | 8 | 0.49970483895242335 | 0.4997048389382419 | 2.8379620727266252e-11 | True | True | PASS |
| local_velocity_x_particle_0 | 1 | -0.0007473733821812486 | -0.0007473733854013176 | 4.308514355257429e-09 | True | True | PASS |
| local_velocity_x_particle_0 | 16 | -0.0007464958392166353 | -0.0007464958373670783 | 2.4776522214472972e-09 | True | True | PASS |
| local_velocity_x_particle_0 | 3 | -0.0007472625978820283 | -0.00074726258514346 | 1.704697702560288e-08 | True | True | PASS |
| local_velocity_x_particle_0 | 5 | -0.0007471508534160365 | -0.0007471508411960315 | 1.6355472269619777e-08 | True | True | PASS |
| local_velocity_x_particle_0 | 8 | -0.0007469802894942592 | -0.0007469803109394491 | 2.8709176793445738e-08 | True | True | PASS |
| physical_viscosity | 1 | -0.0009225487813835777 | -0.0009225488012409855 | 2.15245066624675e-08 | True | True | PASS |
| physical_viscosity | 16 | -0.014744501167383465 | -0.014744501147800904 | 1.328126400797756e-09 | True | True | PASS |
| physical_viscosity | 3 | -0.002767238146810944 | -0.002767238160839014 | 5.069339580822767e-09 | True | True | PASS |
| physical_viscosity | 5 | -0.004611383893364191 | -0.004611383871977459 | 4.637812051610639e-09 | True | True | PASS |
| physical_viscosity | 8 | -0.007376584889745552 | -0.007376584898466376 | 1.1822306026260052e-09 | True | True | PASS |
| reference_density_scalar | 1 | 1.0407145437241826e-07 | 1.0408340855860843e-07 | 0.00011485198607266744 | True | True | PASS |
| reference_density_scalar | 16 | 2.6624858135757892e-05 | 2.6624841220623807e-05 | 6.35313585473329e-07 | True | True | PASS |
| reference_density_scalar | 3 | 9.365211790850524e-07 | 9.365286324225508e-07 | 7.958472640744299e-06 | True | True | PASS |
| reference_density_scalar | 5 | 2.6011672562487642e-06 | 2.601155402182087e-06 | 4.557210478756994e-06 | True | True | PASS |
| reference_density_scalar | 8 | 6.658046266398933e-06 | 6.658035234252679e-06 | 1.6569644926732647e-06 | True | True | PASS |

完成 `20/20`，总判定 **PASS**。每个 case 均在独立短程子进程中执行；1/3/5/8 步采用 1% AD/FD 门，16 步要求 finite/nonzero。邻域整数拓扑选择不可微，本报告不作相反声明。Stage 01C baseline 只读身份由 prerequisite 复核。
