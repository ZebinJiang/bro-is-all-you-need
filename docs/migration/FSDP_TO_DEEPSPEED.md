# FSDP To DeepSpeed Migration

FSDP and FSDP2 are removed from the active M8 registry, presets, packaged
resources, launcher matrix, and CI completion surface. New production configs
must use:

- `single_gpu` for one GPU;
- `distributed_data_parallel` for native data parallel training;
- `deepspeed` with `zero_stage: 1`, `2`, or `3`.

The closest memory-sharding migration target is DeepSpeed ZeRO-3. It remains
CUDA/BF16/NCCL with CPU and NVMe offload disabled. Do not mechanically translate
FSDP state dicts or claim checkpoint compatibility; a separate runtime migration
and parity task is required.

Historical M6/M7 reports, configs, jobs, and logs remain unchanged as evidence.
Their CPU/FSDP outcomes are historical only and do not belong to the active M8
matrix or establish completion.

ZeRO runtime preparation uses only the manual-authorized
`training-deepspeed` uv project, which composes GR00T N1D6, WebDataset, native
training dependencies, and DeepSpeed. Native single-GPU/DDP uses the matching
composition without DeepSpeed. Wave 6 does not create either environment or a
lock; Wave 8 must prepare the selected project and collect its versioned
environment fingerprint before a scheduler submission.
