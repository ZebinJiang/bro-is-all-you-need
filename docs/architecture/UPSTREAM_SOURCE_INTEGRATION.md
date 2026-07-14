# M6 Upstream Source Integration Map

This is the canonical M6 map for source evidence actually available during the
milestone. Upstream repositories and registered archives are evidence only;
AutoVLA does not import them at runtime. An archive digest is not a commit pin,
and an absent archive was not inspected.

| Source evidence | Evidence class | M6 use and local destination | Dependency mode | License and notice status | Deferred boundary |
| --- | --- | --- | --- | --- | --- |
| NVIDIA Isaac-GR00T `n1.6.1-release` at `5dc80c4afd726b34faad1d8f7e007a13b34e4c88` | inspected pinned source; adapted source and reimplementation from contract | isolated Eagle/DiT/embodiment derivatives under `autovla/models/families/gr00t_n1d6/_nvidia/`; owned family code under `autovla/models/families/gr00t_n1d6/` | declared model extra only; no upstream `gr00t` import | NVIDIA restricted source license plus immediate MIT/Apache notices and full texts are recorded in `THIRD_PARTY_NOTICES.md` | authorized official assets and full numerical/checkpoint parity |
| WebDataset repository `e0953f9bba17b416d5792d5a263b171c266e78be`; package `webdataset==1.0.2` | public API integration | local finite/resampled streaming in `autovla/data/backends/webdataset.py` | optional `data-webdataset`; no default | BSD-3-Clause package dependency; no copied source | broader worker/runtime and throughput evidence |
| LeRobot `v0.5.1`, commit `1396b9fab7aecddd10006c33c47a487ffdcb54b4`, dataset format v3.0 | architecture reference and format contract | AutoVLA-owned local reader in `autovla/data/backends/lerobot.py` and `autovla/dataloader/stores/lerobot_v3_reader.py` | optional PyArrow/Pillow route; no LeRobot runtime or Hub | Apache-2.0 reference; no copied LeRobot source | PyAV media materialization and full package parity |
| VLA Foundry `77d2866757b128c77f294d2ad2c5321978943956` | architecture reference | existing strategy, streaming, and telemetry concepts only | none | MIT citation only | source-level or runtime parity |
| RoboDM `f60b3f9cdb5393190cd2d51e238d31002bc2d39a` | architecture reference | AutoVLA-owned container format and grouped-handle reader | none; `robodm_container` remains prototype and not upstream-native | Apache-2.0 citation only | upstream-native compatibility and performance comparison |
| FluxVLA registered archive SHA-256 `aa01ddbd17c33cae95753d3d391f50d94498f5717363cfba1b0a9ed5f793e48d`; archive absent | metadata-level architecture reference | previously recorded collator/runner concepts only; no M6 source adaptation | none | Apache-2.0 metadata; absent archive was not inspected | all symbol-level adaptation and parity |
| Dexbotic registered archive SHA-256 `a5750eadae596bd0bd413ebe51c3e68bd5b589b140d39d3f3e62266427a4dc30`; archive absent | metadata-level architecture reference | previously recorded typed-config/factory concepts only; no M6 source adaptation | none | MIT metadata; absent archive was not inspected | all symbol-level adaptation and parity |
| StarVLA base revision `5e42b775f97d438ae58752f986284da9c4adf98b` | base attribution and architecture reference | protected repository lineage only; AutoVLA owns the current distribution identity | no StarVLA runtime dependency | MIT base attribution | no separate later StarVLA revision is claimed as M6 intake evidence |
| OpenPI license/specification metadata; no exact local source pin or archive | specification reference only | future normalization and family comparison; no M6 code destination | none; no JAX/Flax/OpenPI runtime | Apache-2.0 metadata | all implementation and parity |
| PyTorch `>=2.5,<2.7` selected by task-local runtime resolution | public dependency API | DataLoader, DDP/FSDP2, distributed checkpoint, and tensor runtime | declared `training`/model extras | dependency use; no copied PyTorch source | exact wheel/CUDA identity belongs to runtime evidence |

No FluxVLA, Dexbotic, StarVLA, VLA Foundry, RoboDM, LeRobot, OpenPI, or
WebDataset source block was copied in M6. No dependency, lockfile, upstream
checkout, model weight, tokenizer asset, or dataset artifact is added by this
map. The NVIDIA derivative inventory and exact file-level notices remain
authoritative in `THIRD_PARTY_NOTICES.md`.
