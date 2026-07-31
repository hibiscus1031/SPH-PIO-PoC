# SPH-PIO-PoC — Stage 00 summary

Scope completed: macOS/Apple Silicon audit and minimal PyTorch/MPS availability
testing only. No solver or model was written, system Python was not modified,
and no CUDA, cuDNN, or NVIDIA package was installed.

## Evidence-based decision

| Question | Finding | Evidence |
|---|---|---|
| Suitable for a 2D concept proof? | **Yes, with conservative particle counts.** | Hardware audit records Apple M2, 16 GB unified memory, and an 8-core Metal GPU. The PyTorch test completed all requested CPU/MPS checks. |
| Is CPU usable? | **Yes.** | All CPU tensor, autograd, Linear, MultiheadAttention, scatter/indexing, and cdist/topk tests passed. |
| Is MPS usable? | **Yes.** | `is_built=True`, `is_available=True`, `device_count=1`; all requested MPS checks passed. |
| Key unsupported operators? | **None found in this Stage 00 test set.** | MPS passed arithmetic, autograd, Linear, MHA forward/backward, `scatter_add`, `index_add`, `index_select`, `cdist`, `topk`, and float32 comparison. This is not a blanket claim for every PyTorch/MPS operator. |
| Can diffSPH run directly? | **Installation/import precheck passes; a full solver run remains unverified.** | In a separate Python 3.12 temporary environment, `torchCompactRadius 0.5.5` built as `macosx_11_0_arm64`, imported after declared runtime dependencies were present, and its PointCloud naive neighbor query passed on CPU and MPS. `diffSPH 0.2.2` then installed and imported. No simulation was run in this phase. |
| Need a pure-PyTorch minimal SPH fallback? | **Yes—retain it as the Stage 01 default fallback.** | diffSPH documentation still centers its preferred setup on CUDA and describes its neighborhood component as C++/CUDA-based. Passing import/naive-neighbor probes does not validate all diffSPH solvers or MPS code paths. |

## PyTorch result

The complete, exception-preserving output is in `torch_backend_test.txt`. It
reports `torch 2.13.0`, MPS built and available, and PASS for every requested
operation on both CPU and MPS. Float32 matrix-output consistency reported
`max_abs_error=0.000e+00` for the tested seed and input. MPS memory interfaces
were available; the final test reported `recommended_max_memory=12713115648`
bytes (about 11.84 GiB). This is an allocator recommendation, not a guarantee
that this amount is safely available to one simulation on a 16 GB unified-memory
machine.

## Performance result

The 3-warm-up/8-measurement results are in `backend_benchmark.csv` and
`backend_benchmark.md`. At the tested size, MPS was faster for 1024×1024 matrix
multiplication (1.285 ms forward versus CPU 2.205 ms) but slower for the simple
N=1024, K=32, C=32 neighbor aggregate (1.343 ms versus CPU 0.340 ms). The
small MHA test also favored CPU. These measurements should guide backend choices
only after the real Stage 01 data layout has been profiled.

## diffSPH compatibility precheck

The upstream `requirements.txt` pins torch 2.5.1 with torchvision and torchaudio;
the current installation guide states PyTorch >2.5, Python >3.11, and says that
macOS can work without CUDA, but its preferred instructions install CUDA 12.8
and its source-build description says torchCompactRadius needs GCC and CUDA.

Actual local probing is more encouraging but limited: the resolver accepted
`diffSPH 0.2.2` plus `torchCompactRadius 0.5.5` with macOS ARM64 PyTorch;
torchCompactRadius built locally without requesting CUDA and a CPU/MPS naive
radius-search probe passed. A binary-only request also found the older universal
`torchCompactRadius 0.2.4` wheel. Full terminal output, including two deliberately
isolated probe errors and their complete tracebacks, is preserved in
`diffsph_compatibility_check.txt`.

The first trace is a control import attempted after `--no-deps`; it failed only
because NumPy was intentionally absent, and the subsequent import passed after
installing `torch`, `numpy`, and `scipy`. The second trace came from passing a raw
Tensor to an API revision that expects `PointCloud`; the documented constructor
probe then passed on both backends. Neither is classified as CUDA dependence,
compiler failure, macOS ARM64 absence, or Python-version conflict. The correct
current classification is therefore **“full diffSPH execution: 尚无法判断”**,
despite the positive installation/import/neighbor-search precheck.

## Safe initial scale and next phase

Begin a future 2D prototype at **N ≤ 1,024 particles**, batch size 1, 32
neighbors, and float32—the only particle-scale neighborhood workload actually
timed here. Use a fixed memory/correctness gate before trying 2,048 and then
4,096 particles; do not infer a larger safe count from the MPS memory advisory.

The next phase should define a CPU-reference test matrix and an MPS/CPU fallback
policy for each needed operator, then implement the smallest pure-PyTorch SPH
path only after that design is approved. Before adopting diffSPH for production
experiments, run a small official 2D example in the isolated environment and
record its MPS operator coverage, numerical agreement against CPU, memory use,
and any fallback warnings.
