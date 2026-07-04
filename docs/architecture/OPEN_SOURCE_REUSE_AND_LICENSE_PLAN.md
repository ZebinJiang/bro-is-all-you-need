# Open Source Reuse And License Plan

## Purpose

AutoVLA should reuse mature open-source ideas without importing upstream runtime assumptions into the core training spine. This task adopts inspiration-only reuse: the design learns from upstream structure, but no upstream code is copied, adapted, vendored, or added as a dependency.

## License Matrix

| Reference | License evidence | Local decision | Dependency impact |
| --- | --- | --- | --- |
| StarVLA | Public project/paper metadata and current StarVLA engineering base | Design inspiration for modular training and model/action-head separation | None |
| Dexbotic | Local `code-input/LICENSE_REVIEW.md` records MIT archive license evidence | Design inspiration for registry/factory and layered config patterns | None |
| FluxVLA | Local `code-input/LICENSE_REVIEW.md` records Apache-2.0 archive license evidence | Design inspiration for standardized interfaces and decoupled modules | None |
| VLA Foundry | Upstream `TRI-ML/vla_foundry` license is MIT | Design inspiration for training-stack decomposition and telemetry-aware training | None |
| NVIDIA Isaac-GR00T | Upstream `NVIDIA/Isaac-GR00T` code license is Apache-2.0 | Metadata and adapter-boundary inspiration for `gr00t-n1d6` | None |
| OpenPI | Upstream `Physical-Intelligence/openpi` license is Apache-2.0 | Roadmap metadata inspiration only | None |
| LeRobot | Upstream `huggingface/lerobot` license is Apache-2.0 | Dataset convention inspiration only | None |
| WebDataset | Upstream `webdataset/webdataset` license is BSD-3-Clause | Backend/performance pattern inspiration only | None |

## DataBackend Mixing Action Substrate Decision

No upstream code copied into the reference-guided DataBackend, mixing, or action
schema substrate. The tranche uses native stdlib metadata probes, deterministic
mixing/balancing plan objects, and metadata-only GR00T/OpenPI action schema rows.
It records upstream projects as architecture-guided native implementations,
native metadata probes, or documentation references in
`third_party/reuse_manifest.yaml`.
| Qwen / Qwen-VL | Upstream `QwenLM/Qwen2.5-VL` license is Apache-2.0 | Sample-format and preprocessing discipline inspiration only | None |

## Reuse Modes

- Code copied: none.
- Code adapted: none.
- Runtime wrapper: none.
- Dependency added: none.
- Design inspiration: StarVLA, Dexbotic, FluxVLA, VLA Foundry, GR00T, OpenPI, LeRobot, WebDataset, Qwen.

## Notice And Manifest Policy

Because this task does not copy or adapt upstream source, no
`THIRD_PARTY_NOTICES.md` file is required. The supporting reuse manifest remains
tracked at `third_party/reuse_manifest.yaml` so reviewers can verify inspected
references and no-copy/no-dependency status. If a future task copies, adapts, or
vendors upstream code, that task must add source path, destination path, license,
copyright holder, modification summary, SPDX/notice handling, and test coverage
before publication.

## Whole-Repo Rejection Summary

- StarVLA is useful as a modular research base, but AutoVLA needs governed training infrastructure with fail-closed registry/runtime gates.
- Dexbotic has strong registry and experiment organization ideas, but its broad single-environment toolbox should not define AutoVLA core.
- FluxVLA has useful standard interface naming, but the full data-to-deployment loop is outside this training-spine task.
- VLA Foundry has valuable training-stack and high-throughput data ideas, but AutoVLA must keep family, runtime, and backend choices pluggable.
- GR00T informs family metadata and adapter boundaries, but runtime imports and checkpoint loading require separate env/profile/license gates.
- OpenPI informs future pi-family metadata, but JAX/Flax cannot enter AutoVLA core in this task.
- LeRobot informs dataset conventions, but its trainer is not the AutoVLA training spine.
- WebDataset informs streaming backend design, but AutoVLA core must not become tar-shard-only.
- Qwen informs sample-format discipline, but chat/VL data format does not define robotics action semantics.
