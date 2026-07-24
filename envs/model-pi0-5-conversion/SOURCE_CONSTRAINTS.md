# Pi0.5 Conversion Environment Source Constraints

## Decision

`LOCK_RESOLUTION_ONLY_MATERIALIZATION_AND_CONVERSION_DEFERRED`

This project is an isolated, conversion-only environment for the pinned OpenPI
JAX-to-PyTorch converter. It is not a training or production runtime, and its
resolution is not accepted runtime evidence.

## Source Of Record

- Read-only checkout:
  `/home/cz-jzb/workspace/vla-flywheel/base_model/pi0_5/source/openpi/15a9616a00943ada6c20a0f158e3adb39df2ccac`
- Verified source revision:
  `15a9616a00943ada6c20a0f158e3adb39df2ccac`
- Inspected source files: `pyproject.toml`, `uv.lock`,
  `examples/convert_jax_model_to_pytorch.py`, `LICENSE`, and
  `LICENSE_GEMMA.txt`.
- The source checkout was read only. No OpenPI Python was executed.

OpenPI is Apache-2.0 licensed. `LICENSE_GEMMA.txt` separately governs Gemma
model services and derivatives. This task copies no upstream code and acquires
or mutates no model, checkpoint, tokenizer, or weight payload.

## Python Decision

OpenPI requires Python `>=3.11`, and its pinned lock has an explicit CPython
3.12 Linux resolution branch. The available selected interpreter is CPython
3.12.13 at `/home/cz-jzb/.local/bin/python3.12`, so this project narrows the
requirement deterministically to `==3.12.*`.

## Direct Exact Package Set

| Package | Version | Source-derived need |
| --- | --- | --- |
| `jax` | `0.5.3` | Exact OpenPI project pin and converter checkpoint-array surface. |
| `jaxlib` | `0.5.3` | Exact OpenPI lock companion for JAX 0.5.3. |
| `flax` | `0.10.2` | Exact OpenPI project pin; converter imports `flax.nnx.traversals`. |
| `orbax-checkpoint` | `0.11.13` | Exact OpenPI project pin; converter reads the JAX checkpoint through Orbax. |
| `numpy` | `1.26.4` | Exact pinned lock version used for array transformation. |
| `safetensors` | `0.5.3` | Exact pinned lock version used by the converter output path. |
| `torch` | `2.7.1` | Exact OpenPI project pin used to construct and serialize converted tensors. |
| `transformers` | `4.53.2` | Exact OpenPI project pin required by the imported PyTorch PaliGemma/Gemma model path. |
| `tyro` | `0.9.22` | Exact pinned lock version used by the converter CLI. |

OpenPI's exact `ml-dtypes==0.4.1` and `tensorstore==0.1.74` uv overrides are
retained as resolver overrides. They are transitive compatibility constraints,
not additional direct conversion entrypoints.

Every other transitive package is constrained to the exact version selected by
the pinned OpenPI lock's CPython 3.12 Linux x86_64 branch. This prevents a new
resolution date from silently replacing the source-tested support graph. The
generated `uv.lock` is the authoritative complete exact package set.

## Resolved Lock

- Resolver: `uv==0.11.7`
- Interpreter: `/home/cz-jzb/.local/bin/python3.12` (`CPython 3.12.13`)
- Target: `linux-x86_64`
- Lock SHA-256:
  `17ec3257ec9800a1ab8b22e6f7ba17846911ea60726b6fbf601454083ff33f88`
- Exact dependency packages: `68`
- Virtual project roots: `1`
- Git dependencies: `0`
- Editable dependencies: `0`
- Version drift from the pinned OpenPI CPython 3.12 Linux x86_64 lock
  branch: `0`

Complete exact lock set:

```text
absl-py==2.3.0
certifi==2025.4.26
charset-normalizer==3.4.2
chex==0.1.90
docstring-parser==0.16
etils==1.12.2
filelock==3.18.0
flax==0.10.2
fsspec==2025.3.0
hf-xet==1.1.2
huggingface-hub==0.32.3
humanize==4.12.3
idna==3.10
importlib-resources==6.5.2
jax==0.5.3
jaxlib==0.5.3
jinja2==3.1.6
markdown-it-py==3.0.0
markupsafe==3.0.2
mdurl==0.1.2
ml-dtypes==0.4.1
model-pi0-5-conversion==0.0.0
mpmath==1.3.0
msgpack==1.1.0
nest-asyncio==1.6.0
networkx==3.5
numpy==1.26.4
nvidia-cublas-cu12==12.6.4.1
nvidia-cuda-cupti-cu12==12.6.80
nvidia-cuda-nvrtc-cu12==12.6.77
nvidia-cuda-runtime-cu12==12.6.77
nvidia-cudnn-cu12==9.5.1.17
nvidia-cufft-cu12==11.3.0.4
nvidia-cufile-cu12==1.11.1.6
nvidia-curand-cu12==10.3.7.77
nvidia-cusolver-cu12==11.7.1.2
nvidia-cusparse-cu12==12.5.4.2
nvidia-cusparselt-cu12==0.6.3
nvidia-nccl-cu12==2.26.2
nvidia-nvjitlink-cu12==12.6.85
nvidia-nvtx-cu12==12.6.77
opt-einsum==3.4.0
optax==0.2.4
orbax-checkpoint==0.11.13
packaging==25.0
protobuf==4.25.8
pygments==2.19.1
pyyaml==6.0.2
regex==2024.11.6
requests==2.32.3
rich==14.0.0
safetensors==0.5.3
scipy==1.15.3
setuptools==80.9.0
shtab==1.7.2
simplejson==3.20.1
sympy==1.14.0
tensorstore==0.1.74
tokenizers==0.21.1
toolz==1.0.0
torch==2.7.1
tqdm==4.67.1
transformers==4.53.2
triton==3.3.1
typeguard==4.4.2
typing-extensions==4.13.2
tyro==0.9.22
urllib3==2.4.0
zipp==3.22.0
```

The upstream `jax[cuda12]` extra is deliberately reduced to exact
`jax==0.5.3` plus `jaxlib==0.5.3`: lock resolution and future checkpoint
conversion do not require the JAX CUDA plugin, and this task does not authorize
GPU execution or large GPU-package materialization. Torch remains pinned to
the source's PyPI `2.7.1` package graph; the lock may describe its Linux CUDA
companions, but this task does not synchronize or import them.

## Isolation And Production Contamination

`training-runtime = false` and `production-runtime = false`. This profile has
no dependency on the repository root package and no dependency on
`envs/model-pi0-5`. It must never be synchronized into the production Pi0.5
runtime. In particular, `jax`, `jaxlib`, `flax`, and `orbax-checkpoint` remain
prohibited production dependencies.

The lock authorizes dependency metadata resolution only. It does not authorize:

- environment materialization or large wheel download on the login node;
- converter execution, checkpoint inspection, or output generation;
- model, checkpoint, tokenizer, or weight download or mutation;
- arbitrary pickle loading or `trust_remote_code`;
- GPU, Slurm, training, serving, push, or PR activity.

## Deferred Acceptance

The deterministic lock may be committed, but materialization and conversion are
deferred to separately authorized compute work. `accepted = false` remains
mandatory until that work records interpreter, package-import, input checksum,
Gemma-terms, conversion, output-safetensors, and output-checksum receipts.
