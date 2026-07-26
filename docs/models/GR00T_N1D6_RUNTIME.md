# GR00T N1.6 运行时状态

## M12 packaged profile 历史状态

`gr00t_n1d6_runtime` 固定到 Isaac-GR00T
`5dc80c4afd726b34faad1d8f7e007a13b34e4c88`，使用 CPython 3.10 与
`uv==0.11.7`。deterministic lock SHA256 为
`5daf8f2f83957fae82123c3e1510f57343c231c956939890bc5e803b170dd4e2`。

源码审计和 `uv lock --check` 已通过。Linux x86_64 有效关键包为：

- `torch==2.7.1+cu128`
- `torchvision==0.22.1+cu128`
- `transformers==4.51.3`
- `flash-attn==2.7.4.post1`
- `deepspeed==0.19.2`

M12 当时只证明 resolved candidate lock，没有实现环境。packaged profile 的冻结源码声明
继续保持 literal `runtime_lock_accepted: false`；M13 外部证据不改写这一历史状态或其
fingerprint。

M12 没有 materialize 环境，也没有解释器、完整 distribution 清单、CUDA、
FlashAttention、DeepSpeed 或目标 GPU 环境收据。不得把后续 M13 执行追溯为 M12
已经完成的工作。

## M13 外部环境证据

canonical E9 外部收据在精确 source SHA
`89a28b90a9a5fd70ce8ed08256275c073bd33bb7` 上完成离线 materialize 与独立 verify：

- Slurm job `4849`：`COMPLETED / 0:0`，materialize；
- Slurm job `4850`：`COMPLETED / 0:0`，verify；
- profile fingerprint：
  `bb9df5514d0dcd2e6d7277961bf335ebf5f61e355144a32c1caede4ac41987bb`；
- resolved lock fingerprint：
  `c8b7de93de054ceec4e492b69782191312ca7ef8a6bd611d50c89d02ac6ba0c0`；
- environment receipt fingerprint：
  `93a33948eabffa60ae4f7afa23f43116f09a5f9f8beb8669a775388c4bc1e8f3`；
- installed inventory fingerprint：
  `e7e41dd7a350bb317b995d6a7654e4ee0a816594538e892312eb2a171252f103`。

materialize、verify 与 canonical receipt 的收据内容一致。实现身份为 CPython
`3.10.12`、Torch `2.7.1+cu128`、Torch compiled CUDA `12.8`、loaded CUDA runtime
`12.8`、NVIDIA driver `570.195.03`、cuDNN `9.7.1`、NCCL `2.26.2`、
compute capability `8.0` 和 `NVIDIA A100-SXM4-80GB`。DeepSpeed `0.19.2` 已安装，
environment compatibility observation 为 `true`；这不是 DeepSpeed 训练执行收据。

## 资产与外部门禁

M13 E9 只证明上述精确环境已实现并通过环境验证。checkpoint 相关资产虽然物理存在，
access/terms receipt 仍缺失；E9 没有满足 checkpoint/model mechanics、真实数据、
embodiment 或 dataset-model binding 门禁。

## Runtime acceptance

E9 支持外部 `environment verified` 结论，但没有模型构造、checkpoint 加载、forward、
backward、参数更新、prediction、resume、DDP、DeepSpeed ZeRO 或生产运行收据。因此
该家族仍不能声明 `runtime ready`、`train ready` 或 runtime acceptance。

active zoo 身份为 `gr00t_n1d6`；后端决策保持 literal `NO_BACKEND_WINNER`。
