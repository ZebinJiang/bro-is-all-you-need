# M10 distributed and scaling validation

Distributed validation is gated by official single-GPU real-batch correctness.
That prerequisite was not reached: N1.6 stopped at `BLOCKED_C3_DATA`, while
N1.7 and Pi0.5 stopped at `BLOCKED_ASSET_LICENSE` before runtime.

Consequently none of these cells ran:

- same-node DDP;
- DeepSpeed ZeRO-1, ZeRO-2, or ZeRO-3;
- cross-node DDP or DeepSpeed;
- backend throughput comparison;
- weak or strong scaling;
- GPU utilization, communication, memory, or execution profiling.

The repository contains topology and strategy source paths, and upstream
projects describe some distributed routes. Neither is AutoVLA runtime evidence.
There is no distributed job id, log, output, throughput value, scaling value,
or profiler result to publish for M10.

The accepted precursor is only N1.6 job `3408`: exact canonical HEAD
`ad0fe7074c2a4bd281f6e7ca87caec59a12898f3`, one A100, `COMPLETED 0:0`, strict
checkpoint load passed. Its measured load peak cannot predict training or
distributed memory. The next gate was not submitted because the real candidate
is `demo_bot` `72/98`, lacks production reader metadata/index and a proven
`gr1` mapping, and does not match GR1 `58/29`. See the
[checkpoint evidence](../../runs/tmp/AUTOVLA-M10-ARCHITECTURE-FIRST-PRODUCTION-MODEL-ZOO-GR00T-N1D6-N1D7-PI05-001/compute/m10-cuda-n1d6-c2r7/interpretation.md)
and [C3 blocker analysis](../../runs/tmp/AUTOVLA-M10-ARCHITECTURE-FIRST-PRODUCTION-MODEL-ZOO-GR00T-N1D6-N1D7-PI05-001/compute/m10-cuda-n1d6-c3-ro/execution-plan.md).

This is an honest partial state, not a distributed source pass. A later run may
begin only after a production-readable, immutable real-data receipt enables the
single-GPU batch, update, prediction, and save/resume gate. Distributed cells
then require their own accepted Slurm evidence. `NO_BACKEND_WINNER`.
