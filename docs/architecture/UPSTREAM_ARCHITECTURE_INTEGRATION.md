# Upstream Architecture Integration

M8 adopts bounded contracts, not whole repositories.

| Source pin | Reuse class | Local destination | Not adopted |
| --- | --- | --- | --- |
| NVIDIA Isaac-GR00T `n1.6.1-release` at `5dc80c4afd726b34faad1d8f7e007a13b34e4c88` | adapted isolated source, metadata adaptation, and clean reimplementation by mapped region | `autovla/models/families/gr00t_n1d6/`, generic flow/relative-action components, notices | upstream trainer, launcher, server/client, datasets, dynamic remote code, whole repo, weights, tokenizers |
| DeepSpeed `v0.19.2` at `b919284ab1ad6dbc1cb0e06b10386ff74160b586` | public API integration | `autovla/training/strategy/deepspeed.py`, typed distributed config, `training-deepspeed` | copied runtime, pipeline/tensor parallel, offload, universal env |
| WebDataset `1.0.2`, repository `e0953f9bba17b416d5792d5a263b171c266e78be` | lazy public API integration | `autovla/data/backends/webdataset.py` and data profile | tar-only core, trainer, automatic backend selection |
| LeRobot `v0.5.1` at `1396b9fab7aecddd10006c33c47a487ffdcb54b4` | local format target only | `autovla/data/backends/lerobot.py` and data config | LeRobot package/trainer/runtime dependency |

Exact region-level GR00T/Eagle reuse classes, copyright notices, and local
destinations remain in `THIRD_PARTY_NOTICES.md`; machine-readable pins remain
in `docs/references/upstream_sources.yaml`. Eagle official assets are unresolved
and local-only. No row proves runtime, numerical, gradient, checkpoint, memory,
throughput, or long-training parity.
