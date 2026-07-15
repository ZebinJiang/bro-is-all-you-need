# Upstream Architecture Integration

M9 adopts bounded contracts, not whole repositories.

| Source pin | Reuse class | Local destination | Not adopted |
| --- | --- | --- | --- |
| NVIDIA Isaac-GR00T `n1.6.1-release` at `5dc80c4afd726b34faad1d8f7e007a13b34e4c88` | existing adapted isolated source, metadata adaptation, and clean contract implementation by mapped region | `autovla/models/families/gr00t_n1d6/`, shared R3 transforms, typed local asset bundle, notices | upstream trainer, launcher, server/client, datasets, dynamic remote code, whole repo, new source copy, redistributed weights |
| Physical Intelligence OpenPI at `15a9616a00943ada6c20a0f158e3adb39df2ccac` | architecture mapping and design inspiration only | canonical definitions for `pi0`, `pi0_fast`, and `pi0_5` | OpenPI/JAX/Flax/Orbax runtime, source copy, weights, Gemma assets, network loading |
| DeepSpeed `v0.19.2` at `b919284ab1ad6dbc1cb0e06b10386ff74160b586` | public API integration | `autovla/training/strategy/deepspeed.py`, typed distributed config, `training-deepspeed` | copied runtime, pipeline/tensor parallel, offload, universal env |
| WebDataset `1.0.2`, repository `e0953f9bba17b416d5792d5a263b171c266e78be` | lazy public API integration | `autovla/data/backends/webdataset.py` and data profile | tar-only core, trainer, automatic backend selection |
| LeRobot `v0.5.1` at `1396b9fab7aecddd10006c33c47a487ffdcb54b4` | local format target only | `autovla/data/backends/lerobot.py` and data config | LeRobot package/trainer/runtime dependency |
| StarVLA at `e7a4a7084926a472dc9701acb78f11daebe9dc7e` | protected engineering-base reference | existing `starVLA/` base and AutoVLA extension seams | baseline mutation, direct runtime-parity claim |
| Dexbotic at `0f5ae6382bf0bc6196120f0930ce342ae54e7354` | architecture reference only | layered config, registry, and data ownership boundaries | source copy, dependency bundle, unresolved classifier/license conflict |
| FluxVLA at `68b54062631a8599c655769d14809e02bb7e809c` | architecture reference only | collator, runner, metrics, inference, and hook boundaries | MMEngine runtime, serving, evaluator, source copy |
| VLA Foundry at `77d2866757b128c77f294d2ad2c5321978943956` | architecture reference only | temporal data, mixture, normalization, and telemetry contracts | source copy, resume equivalence, runtime or performance claim |

Exact region-level GR00T/Eagle reuse classes, copyright notices, and local
destinations remain in `THIRD_PARTY_NOTICES.md`; machine-readable pins remain
in `docs/references/upstream_sources.yaml`. A complete declared Eagle support
bundle may be verified and published locally under `base_model/`, but remains
untracked and non-redistributable. OpenPI source is Apache-2.0; model weights and
Gemma terms remain separate. No row proves runtime, numerical, gradient,
checkpoint, memory, throughput, model-quality, or long-training parity.

`NO_BACKEND_WINNER` remains literal.
