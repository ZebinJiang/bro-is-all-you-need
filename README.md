# AutoVLA

AutoVLA is an AI-Native-VLA-Infra engineering workspace for building governed,
observable data, model, and training infrastructure around Vision-Language-Action
research systems.

The active project identity in this repository is AutoVLA. Historical StarVLA
source material remains as upstream attribution and migration context, but the
current engineering dashboard, governance, and benchmark decisions are tracked
under AutoVLA.

## Current Data-Format Dashboard

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
  `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`.

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
