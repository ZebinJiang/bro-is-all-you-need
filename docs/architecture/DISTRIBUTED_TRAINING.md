# Distributed Training

`TrainingTopology` is the canonical Training-owned identity. It records global
rank, local rank, world size, node rank, local world size, launcher, strategy,
NCCL backend, and CUDA device index. Uniform local world sizes and the identity
`rank = node_rank * local_world_size + local_rank` are validated.

Torchrun parsing requires `RANK`, `WORLD_SIZE`, `LOCAL_RANK`,
`LOCAL_WORLD_SIZE`, and `GROUP_RANK`. Direct Slurm parsing requires
`SLURM_PROCID`, `SLURM_NTASKS`, `SLURM_LOCALID`, `SLURM_NODEID`, and a uniform
`SLURM_NTASKS_PER_NODE`. Single GPU uses `direct/single_gpu` with one rank.

The active A100 launcher matrix is:

| Target | Nodes | Ranks | Strategy |
| --- | ---: | ---: | --- |
| `single_gpu` | 1 | 1 | native single GPU |
| `same_node_ddp` | 1 | 2 | DDP |
| `same_node_zero1` | 1 | 2 | DeepSpeed ZeRO-1 |
| `same_node_zero2` | 1 | 2 | DeepSpeed ZeRO-2 |
| `same_node_zero3` | 1 | 2 | DeepSpeed ZeRO-3 |
| `cross_node_ddp` | 2 | 4 | DDP |
| `cross_node_zero3` | 2 | 4 | DeepSpeed ZeRO-3 |

All entries are CUDA/BF16/NCCL with no CPU or NVMe offload. The active matrix
contains only the single-GPU, DDP, and DeepSpeed rows listed above. The Slurm
wrapper only renders by default and delegates an explicit `--submit` to the
existing project submit wrapper.
