# Stage 02M-P — Resource forecast

Zero-step full-batch forward/backward 平均 `0.0837` s，预测 9-run wall `363.4` s、peak RSS `0.726` GiB、checkpoint storage `0.078` GiB。1.5 GiB/10 GiB硬门通过；edge-local O(E d)，无 O(N²) allocation或切图规避，finite completion forecast PASS。
