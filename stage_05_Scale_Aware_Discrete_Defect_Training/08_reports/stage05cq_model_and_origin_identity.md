# Stage 05C-Q Model and Origin Identity

All nine formal models were freshly instantiated on CPU float64 without historical weights. Parameter counts are D1=5762, D2=12098, D3=22978; all trainable elements map exactly once to 2, 3, and 7 frozen groups, including non-overlapping D3 Q/K/V slices. The loss remains Stage 05B `L_def`, with `s_a=3.45632855338432798e-01`, the unchanged `a_cons^star` target, balanced means, complete RK2, and no target value in model tokens.
