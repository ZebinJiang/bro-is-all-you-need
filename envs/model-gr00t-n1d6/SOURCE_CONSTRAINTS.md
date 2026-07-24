# GR00T N1.6 Training Runtime Source Constraints

## Audit identity

- Upstream: NVIDIA Isaac-GR00T `n1.6.1-release`
- Exact commit: `5dc80c4afd726b34faad1d8f7e007a13b34e4c88`
- Audited checkout state: detached exact commit, clean index and worktree
- Upstream `pyproject.toml` SHA256:
  `77472f5d7f65d33b97c51fdeaaafd573020d832c8e377e4b4ddfe8f795ee21b7`
- Upstream `uv.lock` SHA256:
  `13ba5e30069ff7b4dfbf89e0c9808a3c1ce700a64da2bf6acc0efd4ab26021d4`
- Resolver target: `/home/cz-jzb/.local/bin/uv` `0.11.7`

This report is source-derived. Historical installed environments and the
preserved AutoVLA Torch 2.6 lock are not compatibility evidence.

## Upstream constraints

The exact upstream project declares Python `>=3.10,<3.13` and its dGPU path
uses CUDA 12.8. For Python 3.10 on Linux x86_64, the tracked upstream project
and lock establish this coupled model stack:

| Package | Source constraint |
| --- | --- |
| `torch` | `2.7.1`, PyTorch CUDA 12.8 index; lock resolves `2.7.1+cu128` |
| `torchvision` | `0.22.1`, PyTorch CUDA 12.8 index; matching Torch 2.7 line |
| `transformers` | `4.51.3` |
| `flash-attn` | `2.7.4.post1` |
| `triton` | `3.3.1`, supplied by the PyTorch CUDA 12.8 stack on x86_64 |
| `numpy` | `1.26.4` |
| `omegaconf` | `2.3.0` |
| `deepspeed` | `0.17.6` in upstream, not the AutoVLA training-runtime pin |

The upstream Python 3.10 FlashAttention source is an exact wheel URL whose
filename records `cu12`, `torch2.7`, `cxx11abiFALSE`, `cp310`, and
`linux_x86_64`. Upstream's dGPU installer also requires a CUDA 12.8 toolkit and
`libaio-dev` before runtime validation.

The upstream lock contains transitive `safetensors==0.7.0` and
`pillow==12.1.1`, but upstream does not directly pin either package in
`pyproject.toml`. They are therefore observations, not authoritative direct
constraints for the narrower AutoVLA family project.

## Current AutoVLA import surface

The current N1D6 family imports Torch and Transformers directly. Its Eagle
implementation imports Qwen3, SigLIP2, and Qwen2 tokenizer modules from
Transformers. The family factory checks for TorchVision, Pillow, and
safetensors. The shared training strategy lazily imports DeepSpeed and requires
`deepspeed==0.19.2`. The selected data path imports WebDataset, while shared
configuration and tensor/data contracts import OmegaConf and NumPy.

The family runtime therefore needs explicit direct constraints for:

- Torch, TorchVision, Transformers, and the upstream FlashAttention ABI wheel;
- DeepSpeed `0.19.2` as an AutoVLA-owned override of upstream `0.17.6`;
- safetensors and Pillow within the current AutoVLA N1D6 compatibility ranges;
- WebDataset `1.0.2`;
- NumPy and OmegaConf;
- editable local `autovla` without root extras.

## Resolution boundary

The independent project must target only CPython 3.10 on Linux x86_64. It must
not inherit the root `training` extra, because that extra retains the
cross-family Torch `<2.7` range. Every runtime dependency is to be declared
directly in this family project.

Resolution must use PyPI as the default index, the explicit PyTorch CUDA 12.8
index only for Torch and TorchVision, and the exact upstream FlashAttention
wheel URL. Locking must run with builds disabled. No native package build,
CUDA import verification, GPU execution, or DeepSpeed op compilation is
authorized on the login node.

## Resolved package selection

The family project resolved 62 lock records. The direct production training
runtime set is:

| Package | Declared pin | Effective Linux x86_64 lock |
| --- | --- | --- |
| `autovla` | local editable, no extras | `../../` |
| `torch` | `2.7.1` | `2.7.1+cu128` |
| `torchvision` | `0.22.1` | `0.22.1+cu128` |
| `transformers` | `4.51.3` | `4.51.3` |
| `flash-attn` | `2.7.4.post1` | exact upstream CPython 3.10 ABI wheel |
| `deepspeed` | `0.19.2` | `0.19.2` PyPI sdist |
| `safetensors` | `0.5.3` | `0.5.3` |
| `pillow` | `11.3.0` | `11.3.0` |
| `webdataset` | `1.0.2` | `1.0.2` |
| `numpy` | `1.26.4` | `1.26.4` |
| `omegaconf` | `2.3.0` | `2.3.0` |

Relevant transitive locks include `tokenizers==0.21.4` and `triton==3.3.1`.
The lock contains no JAX, JAXlib, Flax, Optax, Orbax, OpenPI, LeRobot,
PyArrow, TensorFlow, TensorRT, upstream `gr00t`, ONNX, or diffusers package.

The lock also contains a TorchVision `0.22.1` aarch64 resolution record from
the PyTorch index. It is inactive under the lock's sole supported marker,
`platform_machine == 'x86_64' and sys_platform == 'linux'`; the effective
target record is `0.22.1+cu128`.

## Resolver and build policy

- Python requirement: `==3.10.*`
- Resolver: uv `0.11.7`
- Default index: PyPI
- Explicit index: `https://download.pytorch.org/whl/cu128`, limited to Torch
  and TorchVision
- Platform: Linux x86_64 only
- Resolution cutoff: `2026-07-24T00:00:00Z`
- Lock SHA256:
  `5daf8f2f83957fae82123c3e1510f57343c231c956939890bc5e803b170dd4e2`
- Lock validation: `uv lock --check` passed with CPython `3.10.12`
- TOML validation: Python 3.12 standard-library `tomllib` parsed both project
  and lock

The first no-build resolution correctly rejected DeepSpeed because
`deepspeed==0.19.2` has no wheel. Final lock generation permitted only
DeepSpeed sdist metadata with `DS_BUILD_OPS=0`; FlashAttention source builds
remained disabled. No package was installed or imported by this resolver.

An attempted read-only `uv tree` against the upstream project was stopped as
soon as uv advanced from direct-wheel metadata retrieval to a TensorRT build
dependency. That command produced no accepted runtime evidence.

## Proposed shared runtime profile

This task does not modify the shared registry. The proposed record is:

```yaml
profile_id: gr00t_n1d6_runtime
profile_kind: training_runtime
uv_project: envs/model-gr00t-n1d6
python: "3.10"
platform: linux_x86_64
cuda_toolkit: "12.8"
torch: "2.7.1+cu128"
torchvision: "0.22.1+cu128"
transformers: "4.51.3"
flash_attn: "2.7.4.post1+cu12torch2.7cxx11abiFALSE"
deepspeed: "0.19.2"
lock_sha256: 5daf8f2f83957fae82123c3e1510f57343c231c956939890bc5e803b170dd4e2
default_sync: manual
lock_status: resolved_candidate
install_status: not_materialized
runtime_receipt_status: absent
accepted: false
```

## Deferred compute gates

Materialization is intentionally deferred. A complete sync would download the
CUDA-enabled Torch stack and the large FlashAttention wheel, while DeepSpeed
is sdist-only. The following gates require an authorized Slurm compute node:

1. install the lock with `DS_BUILD_OPS=0` first and capture a package receipt;
2. verify Torch/TorchVision CUDA 12.8 compatibility and the Torch C++ ABI;
3. import FlashAttention and validate its `cu12`, Torch 2.7, CPython 3.10, and
   `cxx11abiFALSE` wheel against the compute image;
4. import DeepSpeed `0.19.2`, run its op compatibility report, and build only
   explicitly required ops;
5. run bounded AutoVLA N1D6 model, checkpoint, WebDataset, and DeepSpeed
   strategy imports before any training smoke.

Until those gates produce an environment receipt, this artifact is a resolved
and auditable candidate lock, not an accepted production runtime.
