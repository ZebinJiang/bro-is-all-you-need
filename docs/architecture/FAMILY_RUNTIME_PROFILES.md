# Family Runtime Profiles

M11 uses isolated uv projects for `gr00t_n1d6_runtime`, `gr00t_n1d7_runtime`, `pi0_5_runtime`,
and the non-training `pi0_5_conversion` profile. One packaged, read-only JSON descriptor,
`autovla/resources/runtime_profiles/profiles.json`, is the canonical profile source for both
installed and checkout use. `list` and checkout-free `inspect` read only that packaged
descriptor; they do not infer that `site-packages` is a repository checkout. The profile
descriptor digest is exposed for identity checks.

`create`, `verify`, and `exec` require an explicit `--checkout-root`. The manager validates
that root before reading `envs/`, Git source identity, locks, or governed run paths; missing or
false roots fail with stable JSON errors. A checkout-bound `inspect` may additionally report
the observed project and lock state, but that observation does not replace the packaged
descriptor.

Authorized `create` is transactional, atomic, and retryable. It materializes an offline locked
environment under an isolated staging name, writes its identity marker there, and publishes
the canonical target with one atomic rename only after success. Failure leaves no partial
canonical target, records bounded diagnostics under `runs/tmp/`, and permits a later retry
without manual target deletion. Existing YAML profiles are a tested compatibility mirror of
the packaged JSON fields; they are not the canonical M11 registry.

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

These are source and metadata contracts only. No accepted realized family environment,
locked-runtime execution, CUDA evidence, or runtime-readiness promotion is added here. M11
remains Draft-only and `NO_BACKEND_WINNER` remains literal.
