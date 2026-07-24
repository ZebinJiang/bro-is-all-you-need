# GR00T N1.7 Runtime Source Constraints

## Compatibility Decision

`SOURCE_COMPATIBLE_FOR_LOCK_RESOLUTION_RUNTIME_ACCEPTANCE_DEFERRED`

This project resolves one Linux x86_64 production-training lock from the pinned
NVIDIA Isaac-GR00T source revision
`9c7e746b2cd37a810070a98ef41d290a07e806c2`. The source checkout was clean and
its `HEAD` matched that revision when inspected.

The pinned root `pyproject.toml`, `uv.lock`, and installation documentation agree
on CPython 3.12 for the dGPU runtime. The accepted Python range is
`>=3.12,<3.13`, and this lock narrows it deterministically to `==3.12.*`.
The previous local descriptor's Python 3.10 value is rejected as stale and is
not source evidence for N1.7.

The target is Linux x86_64 with CUDA 12.8 PyTorch wheels. Linux aarch64 is an
official upstream platform, but it is intentionally outside this production
training lock because upstream DeepSpeed is x86_64-only. Jetson Orin's separate
Python 3.10 deployment path is also outside this lock.

## Direct Runtime Set

| Package | Constraint | Reason |
| --- | --- | --- |
| `autovla` | local editable checkout | Supplies the current N1D7 model and training implementation without using incompatible root extras. |
| `numpy` | `1.26.4` | Direct N1D7 processor and AutoVLA training import; exact upstream pin. |
| `omegaconf` | `2.3.0` | AutoVLA base runtime dependency; exact upstream pin. |
| `torch` | `2.9.0` | Direct model/training import; Linux wheel must resolve as `2.9.0+cu128` from the explicit PyTorch CUDA 12.8 index. |
| `torchvision` | `0.24.0` | Exact upstream companion for Torch 2.9.0; Linux wheel must resolve as `0.24.0+cu128`. |
| `transformers` | `4.57.3` | Current factory dynamically imports `AutoProcessor`, `AutoConfig`, and `AutoModelForImageTextToText`; exact upstream pin. |
| `safetensors` | `0.7.0` | Current factory/checkpoint path requires the module; exact version observed in the pinned upstream lock. |
| `diffusers` | `0.35.1` | Direct import for the copied NVIDIA DiT attention and embedding components; exact upstream pin. |
| `flash-attn` | `2.8.3` | Required by the factory's `flash_attention_2` selection; use the upstream cp312 Linux x86_64 CUDA 12/Torch 2.9 wheel URL. |
| `deepspeed` | `0.17.6` | Exact upstream training pin and lock resolution for Linux x86_64. |

No JAX, Flax, Orbax, TensorFlow, or family-conversion package is part of this
runtime.

The `[tool.uv].constraint-dependencies` table additionally pins every support
package for which an unconstrained uv 0.11.7 resolution differed from the
pinned official `uv.lock`. These are compatibility constraints, not new direct
runtime requirements. A complete candidate-to-official lock subset audit must
pass before commit.

## Trust Boundary

`trust_remote_code` is always false. The current N1D7 config rejects
`trust_remote_code=True`; both Transformers `from_pretrained` calls explicitly
pass `trust_remote_code=False` and `local_files_only=True`. Lock resolution does
not authorize network model-code loading, checkpoint acquisition, or remote
code execution.

## CUDA And Native Build Policy

- `torch` and `torchvision` use only
  `https://download.pytorch.org/whl/cu128` on Linux.
- `flash-attn` uses the official upstream URL-pinned cp312 Linux x86_64 wheel:
  `flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl`.
- Source fallback for `flash-attn` is not permitted on the login node. The
  upstream build dependencies (`torch==2.9.0`, `numpy==1.26.4`,
  `triton==3.5.0`) are recorded only to keep future lock regeneration aligned
  with the official policy.
- The pinned lock exposes DeepSpeed 0.17.6 only as an sdist. It must not be
  built or imported on the login node. Any native op build belongs to the
  authorized Slurm compute materialization step.

## DeepSpeed Compatibility

The pinned upstream project co-resolves DeepSpeed 0.17.6 with Torch 2.9.0
cu128. Current AutoVLA uses public DeepSpeed surfaces: `initialize`, `zero.Init`,
engine backward/step/checkpoint methods, and public counters. That is sufficient
for a source-level compatibility candidate, not runtime proof.

The shared AutoVLA `training-deepspeed` extra and one missing-dependency error
message still name DeepSpeed 0.19.2. Those declarations are stale relative to
the pinned N1D7 official source and are deliberately not imported into this
independent project. This task does not modify them. Compute validation must
confirm that 0.17.6 satisfies the actual public API calls before the shared
runtime profile can be accepted.

## Deferred Acceptance Gates

The deterministic lock may be committed, but the environment remains
unaccepted until an authorized Slurm compute receipt proves:

1. Python, platform, CUDA driver/runtime, Torch 2.9.0+cu128, and torchvision
   0.24.0+cu128 fingerprints.
2. Imports of `torch`, `torchvision`, `transformers`, `safetensors`,
   `diffusers`, `flash_attn`, and `deepspeed`.
3. FlashAttention 2 operation availability for the target GPU architecture.
4. DeepSpeed 0.17.6 initialization and the AutoVLA ZeRO strategy surface.
5. N1D7 processor/model construction with local assets and
   `trust_remote_code=False`.

Checkpoint, Cosmos asset/license, CUDA operation, and training receipts remain
separate gates. A resolved lock is not an accepted production environment.
