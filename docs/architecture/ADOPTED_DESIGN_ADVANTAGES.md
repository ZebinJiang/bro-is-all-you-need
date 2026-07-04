# Adopted Design Advantages

## AutoVLA-Native Spine

The adopted design keeps the training spine small, typed, and testable. `TrainingBatch` separates Data output from model-family-specific adapters. `RuntimePlan` and `EnvProfile` make runtime activation explicit and fail closed. `EfficiencyTelemetry` makes throughput and latency visible before real training is authorized.

## Extensibility

The model-family registry supports GR00T, π/OpenPI, OpenVLA, Qwen-action, and future families without importing their runtimes into AutoVLA core. Each family can add metadata, dry-run adapters, and later runtime adapters in separate reviewed steps.

## Efficiency

The spine prevents common hot-path mistakes: metadata lookup does not import models, adapters do not read datasets, checkpoint manifests do not write weights, and telemetry separates data wait from compute and loss timing.

## Governance And License Safety

Open-source references are recorded as inspiration-only. No upstream code is copied or adapted, so the PR avoids hidden dependency, notice, SPDX, and model-weight license risk while preserving a path for future licensed reuse.
