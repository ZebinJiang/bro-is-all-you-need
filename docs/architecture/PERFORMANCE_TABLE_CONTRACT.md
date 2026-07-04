# Performance Table Contract

This contract keeps AutoVLA performance evidence table-shaped and reviewable.
Every benchmark tranche must emit structured JSON, CSV, and Markdown tables
rather than prose-only metrics.

## Required Tables

| table | purpose |
| --- | --- |
| Benchmark Matrix | names the family, fixture, steps, repeats, and clock source |
| Throughput Summary | records synthetic samples/batches per second and latency |
| Stage Latency | breaks synthetic dry-run latency into data, adapter, policy, loss, and checkpoint stages |
| Data/IO Summary | states whether real dataset or media IO participated |
| Regression/Gate | records pass/fail gate rows and threshold-facing values |
| Missing Telemetry | labels unavailable real-runtime telemetry as synthetic-only |
| Performance Environment | records CPU-only, no-network, no-Slurm, no-endpoint boundaries |

## Boundary

The Stage 2 training benchmark uses deterministic synthetic telemetry produced
from the existing CPU-only runner dry-run. It is not a real throughput claim,
not a GPU benchmark, not a Slurm job, and not evidence that a real model,
checkpoint, tokenizer, processor, endpoint, robot, or dataset is ready.
