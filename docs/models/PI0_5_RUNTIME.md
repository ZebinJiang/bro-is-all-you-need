# Pi0.5 M12 运行时状态

## Runtime lock

`pi0_5_runtime` 固定到 OpenPI
`15a9616a00943ada6c20a0f158e3adb39df2ccac`，使用 CPython 3.12 与
`uv==0.11.7`。deterministic lock SHA256 为
`289d82b1d894e2aa62851258ebab4b2ecc3111965d1f202bdbf621d220cd4825`，
关键包为 `torch==2.7.1`、`transformers==4.53.2` 和
`deepspeed==0.19.2`。

生产 runtime 明确禁止 `jax`、`jaxlib`、`flax`、`orbax` 与
`orbax-checkpoint`。lock 已解析并通过源码审计，但环境未 materialize、未验证，
`runtime_lock_accepted: false`。

## Conversion lock

`pi0_5_conversion` 是同一 OpenPI pin 的隔离 conversion-only profile。其 deterministic
lock SHA256 为
`17ec3257ec9800a1ab8b22e6f7ba17846911ea60726b6fbf601454083ff33f88`，
固定：

- `jax==0.5.3` 与 `jaxlib==0.5.3`
- `flax==0.10.2`
- `orbax-checkpoint==0.11.13`
- `numpy==1.26.4`
- `torch==2.7.1`
- `transformers==4.53.2`

该 lock 只证明转换依赖图已解析；环境、输入 payload 与 conversion/output receipt 均缺失。
它不是训练或生产 runtime，也不能把 JAX 系依赖带入 `pi0_5_runtime`。

## 资产、条款与数据门禁

checkpoint 与 Gemma 条款收据缺失，dataset-model binding 也未建立。conversion 还缺少
输入 payload 身份、接受的 Gemma 条款、执行收据、输出 safetensors 身份与输出摘要。
OpenPI 的 Apache-2.0 源码许可不能替代 Gemma、tokenizer、checkpoint 或派生权重条款。

## Runtime acceptance

两个环境都未 materialize 或验证，也没有 checkpoint 转换、模型构造、CUDA、DeepSpeed、
forward/backward、训练、推理或生产运行收据。因此不能声明 environment verified、
runtime ready 或 train ready。

active zoo 身份为 `pi0_5`；`pi0` 与 `pi0_fast` 继续 deferred。后端决策保持 literal
`NO_BACKEND_WINNER`。
