# Family Runtime Profiles

M11 uses isolated uv projects for `gr00t_n1d6_runtime`, `gr00t_n1d7_runtime`, `pi0_5_runtime`,
and the non-training `pi0_5_conversion` profile. Listing and inspection are metadata-only.

N1.6 家族合同要求 `torch==2.7.1` 与 `deepspeed==0.19.2`。保留的 `uv.lock` 实际解析
Torch `2.6.0` 且不包含 DeepSpeed；其 SHA256 继续用于审计，但
`runtime_lock_accepted` 为 false，环境创建保持 fail-closed。此前离线 lock 刷新没有产出
可接受替代物，本次也没有生成或修改 lock。family model extra 持有 Torch 精确版本，
`training-deepspeed` 仅持有既有 DeepSpeed pin；N1.6 env 显式选择两者以及
`data-webdataset`，不选择通用 `training` extra。

N1.7, Pi0.5 runtime, and Pi0.5 conversion have no accepted lock and no asserted exact package
set. Their license or conversion blockers remain visible in `list`, `inspect`, and `verify`.
Pi0.5 production runtime prohibits JAX, Flax and Orbax; those packages may only belong to a later
authorized conversion environment.
