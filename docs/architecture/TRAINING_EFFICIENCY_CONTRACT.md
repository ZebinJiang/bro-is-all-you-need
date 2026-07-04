# Training Efficiency Contract

## Goals

Training efficiency is a first-class AutoVLA contract. Even CPU-only smoke tests must keep the hot path observable and prevent hidden data/model/runtime costs.

## Required Telemetry

`EfficiencyTelemetry` records:

- samples per second
- batches per second
- p50 and p95 batch latency
- data wait time
- collate time
- adapter time
- forward time
- loss time
- checkpoint manifest time
- optional memory envelope
- dropped sample count and rejection reason

## Hot-Path Prohibitions

The training hot path must not perform repeated media decode, repeated tokenization, per-step statistics fitting, unbounded Python object assembly, model/runtime import during registry lookup, checkpoint probing during family metadata lookup, dataset schema inference inside the loop, blocking data conversion inside optimizer steps, or hidden CPU/GPU transfer in adapter constructors.

## Benchmark Path

This task does not run Slurm or GPU benchmarks. Future benchmark tasks should compare data wait, adapter, compute, loss, checkpoint, memory, and dropped-sample metrics under a governed compute-node wrapper.

## Data Movement Policy

Data backends should deliver normalized, already-collated `TrainingBatch` objects. Model-family adapters may reshape metadata but must not read external datasets, decode media, download assets, or mutate source data.
