# M3 ZJH Dataset / GR00T Pipeline Readiness

This document records the Data-owned readiness scaffold for `AUTOVLA-M3-ZJH-DATASET-GR00T-PIPELINE-READINESS-001`.

## Status

This is metadata-only readiness support. It does not load GR00T weights, does not execute StarVLA/AutoVLA training, does not decode media, does not read parquet rows, does not fit statistics, and does not convert or generate dataset payloads.

The implemented Data surface is:

- `autovla.dataloader.dataset_artifact.DatasetArtifactV1`
- `autovla.dataloader.dataset_artifact.FingerprintSet`
- `autovla.dataloader.adapters.zjh.ZjhAdapter`
- `autovla.dataloader.adapters.zjh`

## Dataset Artifact v1

`DatasetArtifactV1` is a small JSON-safe record for dry-run dataset previews. It stores:

- `dataset_manifest`: source format, normalized dataset root, metadata counts, split, path templates, and robot/codebase identifiers.
- `modality`: camera, state, action, language, and placeholder index mappings.
- `transforms`: preview-only transform declarations.
- `statistics`: statistics scope and explicit `not_fit` state/action markers.
- `sample_index`: placeholder/fallback index rules from metadata templates.
- `episode_index`: placeholder/fallback episode rules from metadata templates.
- `checksums`: small metadata-file checksums only.
- `fingerprints`: deterministic dataset, transform, and statistics fingerprints.

Fingerprints are computed from canonical JSON-safe data with sorted keys. The dataset root is normalized to a project-relative or logical path, and wall-clock time, mtimes, inodes, temporary paths, and user-specific absolute paths are excluded.

The statistics scope is exactly `action_only`, `vision_language_only`, or `mixed`. Vision-language/dialogue-only data cannot contribute to action normalization statistics. Mixed datasets must explicitly declare the action-statistics subset, and action-only statistics require declared action data.

## ZJH Adapter

The `zjh-adapter` reads only:

- `metadata.json` or `meta/info.json`
- `meta/tasks.jsonl`

If both metadata files exist, their SHA256 checksums must match. The adapter maps the LeRobot-v2-compatible ZJH metadata into:

- three RGB camera feature records with decode deferred;
- `observation.state` as the state vector;
- `action` as the action vector;
- task language from `meta/tasks.jsonl`;
- placeholder sample/episode index fields from metadata.

The adapter exposes `adapter_name`, `adapter_version`, `source_format`, `inspect`, `validate`, `plan_conversion`, `convert_dry_run`, `emit_manifest`, `emit_modality`, `emit_sample_index`, `emit_episode_index`, and `emit_statistics_plan`. Function wrappers remain available and route through the adapter object. Unsupported statistics scopes fail closed. VLM/dialogue-only previews cannot request action statistics.

## Output Boundary

The dry-run writer emits only a small `dataset_artifact.json` under a caller-provided output directory. It refuses writes under `datasets/readonly` and refuses adapter writes inside the dataset root.

## Validation Boundary

The tests use `tmp_path` tiny metadata only. They do not create real media, parquet shards, generated datasets, model artifacts, checkpoints, Slurm jobs, GPU work, training runs, external downloads, or network activity.

## Model Zoo And GR00T N1.6/N1.6.1 Skeleton

The implemented Model surface is:

- `autovla.models.ModelZooEntry`
- `autovla.models.ModelAssetMetadata`
- `autovla.models.get_model_zoo_entry`
- `autovla.models.Gr00tN1D6AdapterSkeleton`

The canonical model registry key is `gr00t-n1d6`. It is metadata-only and records
the Manager-confirmed NVIDIA Isaac-GR00T release reference
`n1.6.1-release` at short commit `5dc80c4`. AutoVLA does not fetch, vendor,
import, or execute that upstream source in this tranche.

The GR00T-series and PI-series names in `autovla.models.registry` are roadmap
metadata. Only `gr00t-n1d6` is currently registered, and it is marked
`unavailable_missing_assets` until a later user-approved task supplies governed
source and checkpoint evidence.

The adapter skeleton fails closed for `forward` and `predict_action` with
`ModelAssetsUnavailableError`. It does not load a model, tokenizer, checkpoint,
dataset row, media file, parquet shard, optimizer, GPU/CUDA path, Slurm job,
Hugging Face/W&B service, endpoint, robot, or training/inference runtime.

## Training Baseline Metrics Summarizer

The Training-owned baseline metrics surface is:

- `autovla.training.baseline_metrics.summarize_baseline_run`
- `autovla.training.baseline_metrics.render_baseline_metrics_markdown`
- `autovla.training.baseline_metrics.write_baseline_metrics_report`

This surface reads only local JSON/text evidence from an authorized GR00T
baseline run directory. It does not inspect checkpoints, dataset payloads, W&B
binary artifacts, Hugging Face caches, model weights, tokenizers, Slurm, GPUs,
or any external service. The parser summarizes observed configuration,
progress, scalar loss/grad/lr metrics, progress throughput, dataloader wait
proxy metrics, warning counts, local W&B file availability, and partial/cancelled
status evidence.

Reportable output is deterministic JSON/Markdown with sensitive values redacted.
Absolute paths, W&B URLs, emails, hostnames, GPU UUIDs, token-like strings, and
other identifying local values are replaced with stable placeholders such as
`<PATH>`, `<RUN_DIR>`, `<URL>`, `<EMAIL>`, `<HOST>`, and `<GPU_UUID>`. Missing
telemetry remains explicit as `missing`, `not_observed`, or `not_parseable`
rather than inferred.

The baseline metrics report for this tranche is written under:

- `runs/tmp/AUTOVLA-M3-ZJH-DATASET-GR00T-PIPELINE-READINESS-001/baseline-metrics-report.md`

This is readiness evidence only. It does not authorize finetune execution or a
model/dataset runtime path.
