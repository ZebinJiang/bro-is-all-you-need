# Third-Party Notices

## M12 当前来源复用记录

本节沿用并保留已固定的来源、版本、许可与版权事实，并按 family source map 校正
N1.7/Pi0.5 的适配和清洁重实现分类。该记录不构成 runtime、GPU、Slurm、checkpoint、
tokenizer、模型权重或 gated asset 的许可证据。

### NVIDIA Isaac-GR00T N1.7

- Repository: `https://github.com/NVIDIA/Isaac-GR00T`.
- Exact source pin: `9c7e746b2cd37a810070a98ef41d290a07e806c2`.
- Checkpoint pin: `nvidia/GR00T-N1.7-3B` at
  `2fc962b973bccdd5d8ce4f67cc63b264d6886495`.
- Source copyright: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES.
- Source license: Apache-2.0; complete text at `licenses/Apache-2.0.txt`.
- Reuse: three family-private files are attributed adaptations, not verbatim
  copies. Their headers preserve NVIDIA copyright, Apache-2.0, exact revision,
  upstream path, Git blob and local modifications:
  - `gr00t/model/modules/dit.py` blob
    `4bb9994d3c89a738a830c5af927b1cd24d2854a5` ->
    `autovla/models/families/gr00t_n1d7/_nvidia/dit.py`;
  - `gr00t/model/modules/embodiment_conditioned_mlp.py` blob
    `504785d57cc33a87613dd775cc415cc88574c2ee` ->
    `autovla/models/families/gr00t_n1d7/_nvidia/embodiment.py`;
  - `gr00t/model/gr00t_n1d7/gr00t_n1d7.py` blob
    `346b597a4b9a115a9a5b1053621f47f07833da09` ->
    `autovla/models/families/gr00t_n1d7/action_head.py`.
- Local modifications: the three headers are authoritative; changes include
  removing upstream mixin/runtime side effects, adding typed AutoVLA
  boundaries, strict validation, shared flow hooks and Chinese documentation.
- Dependency impact: the DiT adaptation uses the already declared
  `diffusers==0.35.1`; the other adaptations use existing family PyTorch/shared
  contracts. This provenance repair adds or changes no dependency.
- Purpose: family-owned Cosmos/Qwen3-VL, processor, action-head, checkpoint and
  assembly contracts.
- Weight/access status: fail closed. The packaged checkpoint terms conflict
  with accompanying publication claims, and Cosmos-Reason2-2B license/access
  receipts are missing.
- Risk: no redistribution, asset bundle, checkpoint execution or runtime claim
  is authorized until canonical receipts resolve the conflict.

### Physical Intelligence OpenPI / Pi0.5

- Repository: `https://github.com/Physical-Intelligence/openpi`.
- Exact source pin: `15a9616a00943ada6c20a0f158e3adb39df2ccac`.
- Source copyright: Physical Intelligence/OpenPI upstream copyright and
  attribution are preserved; no new copyright claim is made.
- Source license: Apache-2.0; complete text at `licenses/Apache-2.0.txt`.
- Reuse: mixed and path-specific. Six source regions are minimally adapted:
  observation preprocessing, tokenizer contract, PyTorch preprocessing, image
  padding, transforms and checkpoint conversion. Eight source regions are
  architecture inspiration for clean AutoVLA implementations: config,
  Pi0/Gemma PyTorch boundaries, normalization, policy and three embodiment
  policies. `LICENSE` is a license reference, not copied or adapted code.
  Exact upstream path/blob/local-path rows live in both family
  `PI05_SOURCE_TO_LOCAL` and the canonical YAML maps.
- Local modifications: adapted regions add typed AutoVLA inputs/outputs,
  strict shape/mask/range checks, immutable normalization receipts,
  deterministic conversion manifests and local-only safetensors boundaries.
  Inspired regions retain no upstream implementation text.
- Purpose: PyTorch Pi0.5 family boundaries, quantile transform contract,
  conversion schema and safetensors-only production load boundary.
- Weight/access status: Gemma, tokenizer, checkpoint and derived-weight terms
  remain separate and unresolved. No local conversion asset exists.
- Dependency impact: JAX, Flax and Orbax remain conversion-only and are not
  production imports; OpenPI is not a runtime dependency; no dependency change
  is included.
- Risk: checkpoint conversion, numerical parity and all GPU/distributed claims
  remain blocked.

### StarVLA Upstream Versus AutoVLA Local Base

- Official upstream: `https://github.com/starVLA/starVLA`, reference commits
  `3422b9f2387b6f682cf02802904a77b23ab13afd` and
  `236f584ef603817e019b002924b2506a71311f2b`, MIT.
- Local Wave 5 engineering base:
  `005da344ac96e0e309fbb8a466905879c67dfff6` in the AutoVLA repository.
- Reuse: architecture reference only in this wave; no StarVLA code copied.
- Required distinction: the local base SHA is not an official StarVLA source
  revision and must never be published as one.

## DeepSpeed 0.17.6 and 0.19.2

- Repository: `https://github.com/deepspeedai/DeepSpeed`
- Profile-selected releases/tags: `v0.17.6` for N1D7 and `v0.19.2` for
  N1D6/Pi0.5.
- Exact 0.19.2 source commit:
  `b919284ab1ad6dbc1cb0e06b10386ff74160b586`.
- PyPI 0.17.6 sdist: `deepspeed-0.17.6.tar.gz`, SHA256
  `b3318064ee5798e8a27d201ea8b888f0439973c4eac9af9ab381dd1862ebdf45`.
- PyPI 0.19.2 sdist: `deepspeed-0.19.2.tar.gz`, SHA256
  `7e854b6ebe3d2bfa239f82958372927631c74e5324c7f08f17ce7ff5f6b06969`
- License: Apache-2.0.
- Reuse mode: direct optional dependency and public API integration only.
- Public APIs used by both exact versions: `deepspeed.initialize`,
  `deepspeed.zero.Init`, `deepspeed.zero.GatheredParameters`, engine
  call/`backward`/`step`/`zero_grad`, accumulation-boundary query, public
  counters, `save_checkpoint`, and `load_checkpoint`.
- Copied runtime code: none.
- Purpose: CUDA/NCCL training with one strategy covering ZeRO stages 1, 2,
  and 3.
- Risk: exact selected/installed version and common public API are checked
  fail-closed, but installation, CUDA extension build, A100 initialization,
  multi-rank stepping, ZeRO lifecycle, and checkpoint restore are
  runtime-deferred.
- Dependency impact: no dependency is added or relocked. N1D7 independently
  selects `deepspeed==0.17.6`; N1D6 and Pi0.5 select
  `deepspeed==0.19.2`. Torch exact versions remain family profile owned.

## Hugging Face Hub 0.30.2

- Package: `huggingface_hub==0.30.2`.
- License: Apache-2.0.
- Reuse mode: optional public API dependency for the explicit
  `asset-acquisition` profile only; no source is copied.
- Runtime boundary: core, config, model imports, and training do not require or
  import this dependency. Production training is offline and local-only.

## NVIDIA Isaac-GR00T N1.6.1

- Repository: `https://github.com/NVIDIA/Isaac-GR00T`
- Branch/tag: `n1.6.1-release`
- Exact pin: `5dc80c4afd726b34faad1d8f7e007a13b34e4c88`
- Root license: NVIDIA License, including the non-commercial research use
  limitation in Section 3.3. The complete pinned text is preserved at
  `licenses/NVIDIA-ISAAC-GROOT-N1D6.txt`.
- Pinned root-license SHA256:
  `564046abbef821cefd5c169d34ee1e96b3dfb72cf0be81de41ef8f4a1323c5a3`.
- Runtime dependency: none. AutoVLA does not import the upstream `gr00t`
  package and does not require the ignored source checkout at runtime.
- Redistribution posture: Section 3.1 permits distribution only under its
  stated license/notice conditions. AutoVLA applies a stricter asset policy and
  does not redistribute or stage official weights, checkpoints, tokenizers, or
  fetched GR00T/Eagle asset bundles.

| Upstream source and coherent region | Local destination | Reuse class | Modifications and architectural reason | Copyright and license | Dependency impact | Deferred validation |
| --- | --- | --- | --- | --- | --- | --- |
| `gr00t/model/modules/embodiment_conditioned_mlp.py`: `CategorySpecificLinear`, `CategorySpecificMLP`, `SinusoidalPositionalEncoding`, `MultiEmbodimentActionEncoder` | `autovla/models/families/gr00t_n1d6/_nvidia/embodiment.py` | `ADAPTED_SOURCE` | Added typed validation, removed dimension-expansion mutation, retained checkpoint-addressable parameter banks, and isolated all derivative code from generic AutoVLA components. | Copyright NVIDIA Corporation and affiliates; pinned root NVIDIA License. Immediate derivative header retained. | PyTorch only through the selected model extra. | Parameter-name, tensor-shape, output, gradient, and checkpoint parity remain deferred. |
| `gr00t/model/modules/dit.py`: timestep embedding, AdaLN, transformer blocks, and `AlternateVLDiT` cross/self-attention cadence | `autovla/models/families/gr00t_n1d6/_nvidia/dit.py` | `ADAPTED_SOURCE` | Replaced Diffusers mixins with directly owned PyTorch modules, preserved 32-layer/32-head/48-dim structure and alternating text/image cross-attention semantics, removed device probing and environment dispatch. | Copyright NVIDIA Corporation and affiliates; pinned root NVIDIA License. Immediate derivative header retained. | Removes the upstream Diffusers runtime coupling; uses PyTorch only. | Upstream tensor, attention-kernel, numerical, gradient, memory, throughput, and checkpoint-key parity remain deferred. |
| `gr00t/model/modules/nvidia/Eagle-Block2A-2B-v2/configuration_eagle3_vl.py`: Eagle composite configuration | `autovla/models/families/gr00t_n1d6/_nvidia/eagle/configuration.py` | `ADAPTED_SOURCE` | Replaced `PretrainedConfig`/`auto_map` dispatch with a frozen local JSON parser that ignores executable mapping metadata and accepts only Qwen3 plus SigLIP2. | No separate upstream header at the pin; pinned root NVIDIA License applies. Immediate derivative header added. | Standard library only until family construction. | Local JSON compatibility with an authorized checkpoint remains deferred. |
| `gr00t/model/modules/nvidia/Eagle-Block2A-2B-v2/modeling_eagle3_vl.py`: Qwen3/SigLIP2 construction, vision projection, image-token replacement | `autovla/models/families/gr00t_n1d6/_nvidia/eagle/modeling.py` | `ADAPTED_SOURCE` | Removed PEFT, generation, distributed side effects, `AutoModel`, remote code, and unsupported architectures; directly constructs locally owned Qwen3/SigLIP2 class boundaries and returns hidden features only. | Copyright (c) 2025 NVIDIA; immediate MIT notice retained verbatim. Complete MIT text at `licenses/MIT.txt`. | Uses declared PyTorch and Transformers model extra; no upstream or Hub dependency. | Eagle feature, pixel-shuffle, token replacement, checkpoint-key, bf16, and numerical parity remain deferred. |
| `gr00t/model/modules/nvidia/Eagle-Block2A-2B-v2/processing_eagle3_vl.py` and `chat_template.json`: local tokenizer, user-conversation, text/image ordering, and image-marker responsibilities | `autovla/models/families/gr00t_n1d6/_nvidia/eagle/processing.py` | `ADAPTED_SOURCE` | Reads the required local chat template, applies it to one user message containing text followed by ordered images, expands each rendered `<image-N>` marker in place to the exact visual-token count, and left-pads the result. Removed requests, URL images, Hub resolution, dynamic processor dispatch, and server/generation features. | Copyright 2024 The HuggingFace Inc. team; Apache-2.0 header retained verbatim. Complete text at `licenses/Apache-2.0.txt`. | Uses the declared Transformers model extra; no requests or network dependency. | Token IDs and exact upstream processor numerical parity remain deferred. |
| `gr00t/model/gr00t_n1d6/gr00t_n1d6.py`: flow loss/sampling and model responsibility boundaries | `autovla/models/families/gr00t_n1d6/action_head.py`, `model.py`; `autovla/models/components/flow_matching.py` | `REIMPLEMENTED_FROM_CONTRACT` | Clean AutoVLA implementation using typed outputs and generic flow helpers; preserves Gaussian noise, beta time, linear interpolation, `action-noise` velocity, valid-count masked MSE, and four Euler steps. No upstream source text is retained in these files. | Original AutoVLA code under the repository license; NVIDIA terms do not apply to these clean files. | PyTorch only. | Numerical, gradient, RNG, mask, and action-sampling parity remain deferred. |
| `gr00t/model/gr00t_n1d6/processing_gr00t_n1d6.py`, `gr00t/data/state_action/state_action_processor.py`, `gr00t/data/state_action/action_chunking.py`, and `gr00t/data/state_action/pose.py`: processor and relative-pose contracts | `autovla/models/families/gr00t_n1d6/processor.py`, `config.py`, `autovla/models/components/relative_actions.py` | `REIMPLEMENTED_FROM_CONTRACT` | Clean typed conversion from canonical `TrainingBatch`; explicit camera order, normalization, strict padding/masks, typed joint additive policy, and real EEF `T_ref^-1 @ T_action` / `T_ref @ T_relative` composition for homogeneous, xyz+rot6d, and xyz+rotvec formats. No upstream source text is retained. | Original AutoVLA code under the repository license. | PyTorch through the selected model extra; no SciPy dependency. | Camera augmentation, normalization, SE(3) numerical, tokenizer, and shape parity remain deferred. |
| `gr00t/model/gr00t_n1d6/gr00t_n1d6.py` state-dict namespace and Hugging Face local checkpoint layout | `autovla/models/families/gr00t_n1d6/checkpoint.py` | `METADATA_ADAPTATION` | Added local-only discovery, exactly-one-format policy, safe tensor-only load, recognized wrapper stripping, explicit conditioner mapping, collision/shape rejection, strictness modes, and provenance hashes. | Original AutoVLA adapter code; source namespace facts from the pinned NVIDIA-licensed work are recorded here. | Optional `safetensors` only for that local format; PyTorch `weights_only=True` for `.bin`/`.pt`. | Real checkpoint inventory, key/shape/load, dtype/device, and output parity remain deferred. |
| Transformers Qwen3, SigLIP2, and Qwen2 tokenizer public classes used by the local Eagle implementation | `_nvidia/eagle/modeling.py`, `_nvidia/eagle/processing.py` | `PUBLIC_API_INTEGRATION` | Direct class construction replaces checkpoint-controlled `Auto*` dispatch. No Transformers source file is copied beyond the immediate Eagle-derived regions listed above. | Transformers package licensing applies to the installed dependency; applicable immediate Eagle MIT/Apache notices are preserved above. | Declared optional Transformers dependency. | Supported-version/API compatibility remains deferred. |

## Excluded Upstream Material

No upstream `ModelPipeline`, Hugging Face Trainer, launcher, policy server or
client, dataset, example, deployment stack, dynamic modality importer, model
weight, checkpoint, tokenizer asset, media file, or whole repository subtree is
included. The ignored intake checkout is provenance evidence only and must not
be staged or used as a runtime dependency.
