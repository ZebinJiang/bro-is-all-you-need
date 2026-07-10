# AutoVLA

AutoVLA is an AI-Native-VLA-Infra engineering workspace for building governed,
observable data, model, and training infrastructure around Vision-Language-Action
research systems.

The active project identity in this repository is AutoVLA. Historical StarVLA
source material remains as upstream attribution and migration context, but the
current engineering dashboard, governance, and benchmark decisions are tracked
under AutoVLA.

## Current Data-Format Dashboard

## M4 Modular Skeleton

M4 adds one config-driven local dry-run path through `autovla.training.runner`
for the explicit backend keys `webdataset_tar` and `robodm_container_v1`.
`robodm_style` is an explicit alias only. Both routes build the same seed-11
logical fixture, normalize existing store output into the canonical
`TrainingBatch`, use the deterministic `test_double` profile, compute strict
masked loss, emit synthetic stage-separated telemetry, and write metadata-only
checkpoint manifests.

The result is semantic integration evidence, not a performance comparison.
Decision: `NO_BACKEND_WINNER`. Neither backend is a default, recommendation, or
production selection. GR00T N1D6, Pi0, and Pi0.5 remain metadata-only; this path
does not perform real training, gradients, model/checkpoint/tokenizer loading,
HF/W&B/network access, GPU/Slurm work, endpoint access, or robot actions.

Presets:

- `configs/training/modular_skeleton_webdataset.yaml`
- `configs/training/modular_skeleton_robodm.yaml`

The active M3 data-format suite prepares comparable candidates for the next
formal telemetry or training-dataloader run. It does not choose the permanent
training backend, does not start fine-tuning, and does not load a model,
checkpoint, tokenizer, Hugging Face asset, W&B service, endpoint, or robot.

| Candidate | Current role | Status for this suite | Notes |
| --- | --- | --- | --- |
| Raw ZJH / LeRobot v2.1 | Source baseline | Baseline comparator | Read-only source under `datasets/readonly/**`; no source mutation. |
| WebDataset-native | First-class AutoVLA candidate | Productionized candidate | PR #19 selected WebDataset-native as the fastest measured candidate; final backend choice is still deferred. |
| Robo-DM-style | First-class AutoVLA candidate | AutoVLA-owned candidate | Retained because PR #19 showed it was close; this is not a claim of upstream Robo-DM package support. |
| LeRobot v3 | Required comparison route | Dependency decision path | Must either run through an approved local dependency route or record an explicit dependency-blocked decision. |

Detailed dashboard: [Data Format Pipeline Suite](docs/benchmarks/DATA_FORMAT_PIPELINE_SUITE.md)

Benchmark index: [docs/benchmarks/](docs/benchmarks/)

Process archive: [docs/process/](docs/process/)

Architecture docs: [docs/architecture/](docs/architecture/)

## Current Evidence

- PR #19 selected WebDataset-native from bounded native-loader timing evidence.
- Robo-DM-style remains a close first-class candidate for the next comparison.
- Raw ZJH / LeRobot v2.1 remains the source baseline.
- `webdataset_streaming` and WebDataset-native evidence remain decision-support
  inputs, not final training-backend selection.
- LeRobot v3 remains required as a comparison route, with dependency status
  recorded fail-closed when a local approved implementation is not available.
- Generated candidate stores are ignored artifacts under `datasets/working/**`;
  they are not committed as product source.
- Final decision class: `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`.
  This is the historical pre-PR30-final-dataloader root-dashboard decision
  class retained for policy-test compatibility.
- No converted backend winner, final backend winner, or training format has been
  selected.
- Next action:
  `AUTOVLA-M3-GR00T-N1D6-RAWPATH-FINETUNE-TELEMETRY-DRYRUN-001` remains the
  historical next telemetry task before any fine-tune or final backend claim.
- UV environment gate next action:
  `AUTOVLA-M3-GR00T-N1D6-WEBDATASET-TELEMETRY-DRYRUN-ENV-GATE-001` is the next
  post-matrix governance task for the WebDataset telemetry route. It is an
  environment-readiness gate only and does not start fine-tuning.
- PR #30 prior multiformat benchmark numbers are invalidated because the raw
  row used preloaded SourceSample lookup and camera_refs instead of a fair
  materialized native loader. Those numbers must not be used for backend
  selection.
- The corrected PR #30 rerun is the fair native-loader bakeoff under
  [docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V1.md](docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V1.md).
  It requires all candidates to load identical materialized RGB/state/action
  payloads with worker_count=8. The corrected conclusion remains
  `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY` for that historical V1 surface.
- PR #30 adapter audit treats that corrected V1 result as the adapter-v0
  baseline and records bounded adapter-v1 profiling under
  [docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md](docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md)
  and
  [docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V2.md](docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V2.md).
  Adapter-v1 evidence is diagnostic only: it records
  `worker_count_label=configured_8` and `actual_worker_count=not_measured`,
  does not run GPU200/Slurm/training, and does not select a final backend
  winner.
- PR #30 actual dataloader worker benchmark is the replacement evidence surface
  for adapter-v1 diagnostic numbers. The tracked status page is
  [docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md](docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md).
- Compute-W2 completed the bounded final dataloader performance matrix through
  the project Slurm wrapper on job `2488` using the readonly ZJH source dataset.
  Primary runnable ranking by `samples_per_sec`: D4 WebDataset tar
  `501.775424`, D5 RoboDM-style container `295.03279`, D3 local-v3
  `203.022981`, D1b/D2 AutoVLA v2.1 adapter `24.7923`.
- PR #30 decision status:
  `NO_BACKEND_WINNER_INSUFFICIENT_NATIVE_V21_AND_METRICS`. No backend winner,
  training format, fine-tune readiness, model quality, deployment readiness, or
  production readiness is selected. D1a remains
  `NOT_RUN_UNSAFE_OR_UNAVAILABLE`, D6 remains `NOT_IMPLEMENTED_IN_CURRENT_PR`,
  and prompt-contract missing telemetry remains blocking. Tracked status:
  [docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md](docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md).
  Detailed final evidence draft:
  `docs/benchmarks/PR30_FINAL_DATALOADER_PERFORMANCE.md` (new Markdown files
  are ignored by default and require Quality publication handling if they should
  become PR-visible).

## Boundaries

- No real training is authorized by this README.
- No model, checkpoint, tokenizer, external dataset, W&B, Hugging Face, endpoint,
  robot, or deployment behavior is authorized by this README.
- PR #16 remains a draft backend research artifact and is not mutated by the
  data-format pipeline suite.
- Final backend selection is deferred to a future formal telemetry run.
- Root branch mode is the default when root is clean and synced; new worktrees
  are not created by default for process/archive tasks.
- Environment work should use explicit uv profiles rather than a universal
  all-model-zoo environment.

## Historical Attribution

This repository was seeded from the StarVLA research codebase. StarVLA names,
links, and references may remain in historical source, examples, and attribution
contexts, but they are not the active project brand for the governed AutoVLA
milestone work.
