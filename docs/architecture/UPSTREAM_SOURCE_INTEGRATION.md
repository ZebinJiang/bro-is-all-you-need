# Upstream Source Integration Map

This is the canonical M5 source map. Upstream checkouts are evidence only and
are never imported at AutoVLA runtime.

| Source and pin | Reuse class | Source path or symbol | AutoVLA destination | Modification and dependency impact | License and notice | Deferred validation |
| --- | --- | --- | --- | --- | --- | --- |
| NVIDIA Isaac-GR00T `5dc80c4afd726b34faad1d8f7e007a13b34e4c88` | selective isolated adaptation | N1.6.1 Eagle, DiT, flow matching, embodiment, processor and checkpoint units | `autovla/models/families/gr00t_n1d6/**` | AutoVLA interfaces, strict masks, local-only assets; GR00T optional extra | NVIDIA License plus immediate Apache-2.0/MIT notices; recorded in existing notices/licenses | model construction, numerical and checkpoint parity |
| FluxVLA `68b54062631a8599c655769d14809e02bb7e809c` | architecture reference and contract reimplementation | collators, runner ordering, strategies, optimizer grouping, telemetry | `autovla/data/**`, `autovla/training/**` | no FluxVLA dependency or runtime import | Apache-2.0 root plus file-level notices; no Integration code copied | lifecycle and distributed parity |
| StarVLA `3422b9f2387b6f682cf02802904a77b23ab13afd` | architecture reference | framework assembly, local-import factories, training scripts, LeRobot paths | model registrations, DataModule and TrainingEngine contracts | no StarVLA runtime dependency | MIT root plus file-level notices; no Integration code copied | heterogeneous data and training behavior |
| Dexbotic `0f5ae6382bf0bc6196120f0930ce342ae54e7354` | architecture reference | layered config and registry structure | named presets and lazy registries | no dependency | MIT; citation only | config composition runtime inspection |
| VLA Foundry `77d2866757b128c77f294d2ad2c5321978943956` | architecture reference | strategy and streaming boundaries | Training strategy and Data boundaries | no dependency | MIT; citation only | strategy and stream runtime behavior |
| OpenPI `15a9616a00943ada6c20a0f158e3adb39df2ccac` | specification reference | normalization and family metadata | normalization contracts and Pi specifications | Pi remains specification-only | Apache-2.0; citation only | any future Pi implementation |
| LeRobot `1396b9fab7aecddd10006c33c47a487ffdcb54b4` (`v0.5.1`) | architecture reference | local dataset schema and sampling | `autovla/data/datasets/local_lerobot.py`, sampling contracts | optional local data route only | Apache-2.0; citation only unless later adapted | schema and sample-order parity |
| WebDataset `e0953f9bba17b416d5792d5a263b171c266e78be` (package `1.0.2`) | public API integration | local shard reader API | canonical `webdataset` backend delegating existing stores | `data-webdataset`; no default | BSD-3-Clause package dependency | real shard iteration and worker parity |
| RoboDM `f60b3f9cdb5393190cd2d51e238d31002bc2d39a` | architecture reference | container lifecycle and grouped reads | canonical `robodm_container` adapter | AutoVLA-owned prototype, no dependency | Apache-2.0; citation only | grouped-read correctness and performance |

No code was copied or adapted by Integration-W1. NVIDIA-derived files,
copyright statements, notices, and license texts are prior Model-writer output
and remain byte-for-byte preserved. Optional dependencies are bounded in
`pyproject.toml`; no Git source, upstream checkout, hidden lock resolution, or
universal environment is introduced.
