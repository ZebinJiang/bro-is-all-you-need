# Pi0.5 Production Training Runtime Constraints

## Scope

This lock is the JAX-free production training environment for AutoVLA Pi0.5.
Checkpoint conversion is intentionally excluded and must be resolved in the
separate `model-pi0-5-conversion` project. The source of record is the read-only
OpenPI checkout at revision
`15a9616a00943ada6c20a0f158e3adb39df2ccac`.

## Python Compatibility Decision

- OpenPI `pyproject.toml` requires Python `>=3.11`.
- The pinned OpenPI `uv.lock` contains an explicit Python 3.12 Linux resolution
  branch.
- The selected project-local interpreter is CPython 3.12.13 at
  `/home/cz-jzb/.local/bin/python3.12`.
- This profile therefore requires Python `==3.12.*`. The former Python 3.10
  placeholder was incompatible with the pinned source declaration and is not
  retained as a fallback.

## Direct Exact Package Set

| Package | Version | Source-derived need |
| --- | --- | --- |
| `numpy` | `1.26.4` | Pinned lock and current AutoVLA Pi0.5 tensor/image preprocessing imports. |
| `torch` | `2.7.1` | Pinned OpenPI project and lock; current AutoVLA Pi0.5 model and training mechanics. |
| `transformers` | `4.53.2` | Pinned OpenPI project/lock and PyTorch Gemma/PaliGemma imports; current local tokenizer construction. |
| `safetensors` | `0.5.3` | Pinned lock and current strict local checkpoint loader. |
| `deepspeed` | `0.19.2` | Current AutoVLA DeepSpeed strategy's exact runtime guard and future ZeRO 1/2/3 mechanics. |

The current worktree's editable `autovla` package is also a direct project
dependency so the environment lock remains bound to the application source.
Its ordinary `numpy` and `omegaconf` dependencies are resolved transitively
inside the same lock.

## JAX-Family Prohibition

Production training prohibits `jax`, `jaxlib`, `flax`, `orbax`, and
`orbax-checkpoint` as direct or transitive packages. The pinned OpenPI
`scripts/train_pytorch.py` still enters JAX-backed configuration and data-loader
modules, so that script is source evidence rather than the AutoVLA production
entrypoint. JAX/Flax/Orbax checkpoint conversion belongs only in the separately
resolved conversion environment.

## CUDA And DeepSpeed Policy

The lock uses the PyPI `torch==2.7.1` Linux x86_64 wheel policy. For Linux
x86_64, the resolved graph must retain Torch's exact CUDA 12.6 component
dependencies and must not substitute a CPU-only or alternate CUDA index.
`deepspeed==0.19.2` must resolve against the same `torch==2.7.1` graph.

Login-node resolution and bounded no-build materialization do not prove CUDA or
DeepSpeed execution compatibility. Acceptance still requires authorized
compute-node receipts for Torch CUDA import/device visibility, a Pi0.5
forward/backward/update, and DeepSpeed ZeRO 1/2/3 imports and execution.

## Proposed Shared Runtime Profile Record

The shared registry is not modified by this task. The proposed later record is:

```yaml
runtime_profile_id: pi0_5_runtime
runtime_family_key: pi0_5
runtime_profile_kind: training_runtime
uv_project: envs/model-pi0-5
python_version: "3.12"
python_implementation: CPython
platform_intent: linux-x86_64
resolver_name: uv
resolver_version: "0.11.7"
upstream_revision: 15a9616a00943ada6c20a0f158e3adb39df2ccac
runtime_lock_status: lock_resolved_compute_validation_deferred
runtime_lock_sha256: 289d82b1d894e2aa62851258ebab4b2ecc3111965d1f202bdbf621d220cd4825
runtime_lock_accepted: false
exact_packages:
  - deepspeed==0.19.2
  - numpy==1.26.4
  - safetensors==0.5.3
  - torch==2.7.1
  - transformers==4.53.2
prohibited_packages:
  - jax
  - jaxlib
  - flax
  - orbax
  - orbax-checkpoint
requires_cuda: true
default_sync: manual
```

The proposed record intentionally keeps `runtime_lock_accepted: false` until
the deferred compute receipts pass.
