# AutoVLA Training Framework

## Composition and plans

`autovla-train` / `python -m autovla.cli.train` is the sole production training
composition root. `ExperimentConfig` strictly owns these groups:

```text
run, data, model, transforms, topology, training, optimization,
checkpoint, telemetry, inference, deployment
```

Unknown keys fail closed. Named presets layer deterministically, dotted CLI
overrides are validated after materialization, and serialization/fingerprinting
performs no download or model import. Legacy runner/acceleration/nested training
fields are one-way input translations; resolved output contains only canonical
groups.

The composition root resolves immutable `DataPlan`, the R4
`ModelAssemblyPlan` handoff, `TopologyPlan`, `OptimizationPlan`,
`CheckpointPlan`, `TelemetryPlan`, and final `TrainingPlan`. Its identity covers
config, source/manifest/mixture/transform/statistics, family/assets/checkpoint,
strategy/precision, optimizer/scheduler, callbacks, logger, and provenance.
Checkpoint metadata can preserve these identities and supported mixer/loader
state without claiming a distributed resume matrix. The CLI stores the full
immutable `TrainingPlan` in checkpoint provenance. After `DataModule.setup`,
save and resume also bind the resolved `DatasetManifest`, per-source,
transform, and statistics fingerprints into checkpoint compatibility; a changed
runtime data identity fails closed before state application.

## One engine, strategy-owned operations

Exactly one `TrainingEngine` owns batch lifecycle, processor calls, state,
callbacks, telemetry, checkpoint cadence, stopping, and cleanup. A prepared
session/strategy owns device/distributed preparation, autocast, backward,
accumulation boundaries, clipping, optimizer/scheduler step, overflow/skip, and
strategy-native checkpoint operations. DeepSpeed uses its official engine
`backward`, `step`, `save_checkpoint`, and `load_checkpoint`; the engine does not
step the optimizer a second time.

Active registry keys are exactly `single_gpu`, `distributed_data_parallel`,
`deepspeed_zero_1`, `deepspeed_zero_2`, and `deepspeed_zero_3`.

The family processor records rank-local `DataTelemetryRecord` values for
dataset and embodiment sample/batch counts, requested/effective weights and
deviations, skips, data wait, optional decode/collate timing, valid image/token/
action elements, rank/world-size, source fingerprints, and transform
fingerprint. The existing logging callback cadence aggregates local steps; when
`telemetry.reduce_across_ranks=true`, the existing prepared session collective
produces one primary-rank `reduced_sum` record. The pending local accumulator is
part of logger checkpoint state. This adds no engine, session, backward, or
optimizer-step owner.

Production model training is CUDA-only. CPU remains valid for configuration,
metadata, indexing, hashes, data workers, and tests. Canonical training presets
select only the five registry keys listed above. Remote telemetry is unsupported;
canonical telemetry is local-only.

No GPU, DDP, ZeRO, resume-parity, throughput, model-quality, or backend-winner
result is claimed by this R10 source repair. `NO_BACKEND_WINNER`.
