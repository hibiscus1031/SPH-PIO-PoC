# Stage 05C Models and Parameter Groups

Fresh D1/D2/D3 models were instantiated at seeds 20500501, 20500502, and 20500503 without checkpoint or historical-weight reads. Parameter counts are D1=5762, D2=12098, and D3=22978. All trainable elements map uniquely and completely to 2, 3, and 7 actual optimizer-aligned groups; D3 Q/K/V use frozen non-overlapping slices.
