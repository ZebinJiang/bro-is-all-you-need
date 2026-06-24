# Config Contracts

## Project config

`configs/project.json` defines project identity, baseline registry policy, actual-layout integration rules, dataset directories, and external path policy. It must not be used to silently change or weaken protected baseline behavior.

Required fields:

- `schema_version`
- `project_key`
- `project_name`
- `project_scope`
- `baseline_registry_policy`
- `source_layout_policy`
- `default_output_root`

## Baseline registry contract

Future baseline registry entries should specify:

- `baseline_id`
- `family`
- `implementation_status`: `planned`, `stub`, `integrated`, `validated`, `deprecated`
- `source_paths`
- `config_paths`
- `checkpoint_assets`
- `tokenizer_assets`
- `dataset_requirements`
- `protected_paths`
- `enabled_by_default`
- `validation_evidence`
- `rollback_notes`

Family names alone do not imply implementation. Direct protected-path edits require explicit task scope, rationale, validation evidence, and rollback notes.

## Experiment config

Experiment configs live under `configs/experiments/` and should specify:

- `experiment_key`
- `description`
- `mode`: `mock`, `integration`, `dataset_conversion`, `training`, `evaluation`, `inference`, `serving`
- `baseline_reference`
- `dataset_reference`
- `model_or_backbone_reference`
- `tokenizer_reference`
- `parameters`
- `output_policy`

## Dataset conversion config

Dataset conversion or indexing configs should specify:

- `source_reference`
- `source_format`: `LeRobot`, `Parquet`, `RLDS`, `HDF5`, `robot_logs`, `simulation_rollouts`, or another documented format
- `destination_root`: `datasets/working` or `datasets/cache`
- `manifest_path`
- `checksum_policy`
- `sampling_or_filtering_policy`
- `reproducible_command`

Original source files remain immutable under `datasets/readonly/`.

## Inference and serving config

Inference or serving configs should specify:

- `baseline_reference`
- `checkpoint_reference`
- `tokenizer_reference`
- `input_protocol`
- `output_protocol`
- `latency_metric`
- `throughput_metric`
- `resource_requirements`
- `safety_boundary`
- `credential_policy`

Robot endpoints, private services, and credentials require explicit user authorization.

## Slurm config

Slurm configs live under `configs/slurm/` and should specify resources and approved cluster assumptions. Do not encode secrets.

Required fields:

- `job_name`
- `approved_cluster`
- `partition`
- `nodes`
- `ntasks`
- `cpus_per_task`
- `mem`
- `gres`
- `max_minutes`

If `approved_cluster` or `partition` is `TO_FILL`, the Manager must run Slurm environment discovery before formal submission. After discovery fills these fields, do not update them unless the user explicitly requests a refresh.

## Debug profile config

`configs/slurm/debug_profiles.json` defines compute-node debug allocation profiles for `scripts/slurm/request_compute_debug.sh`.

The default profile is minimal: 1 CPU, 4G memory. The `h800-gpu` profile records the user-provided debug shape: partition `h800`, 16 CPUs, 64G memory, one GPU, one hour.
