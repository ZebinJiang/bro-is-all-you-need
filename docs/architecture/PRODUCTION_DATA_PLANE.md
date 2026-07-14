# Production Data Plane

## M8 Topology Delta

`TrainingEngine` now projects the canonical typed Training topology into the
Data-owned `PartitionContext`. Data receives rank, local rank, world size, node
rank, local world size, launcher and strategy identity, plus its existing
worker id/count facts. `autovla.data` does not import Training or DeepSpeed, and
no backend branches on strategy name. Same-node and cross-node-like partition
facts use the same deterministic rank/worker Cartesian partition.

This delta changes no backend implementation and runs no benchmark. The active
decision remains `NO_BACKEND_WINNER`.

## Historical M6 Data Evidence

M6 defines immutable source specifications, worker context, partition plans,
temporal queries, and next-unread loader state. Map sources are divided by rank
once and dispatched by PyTorch workers once. Streaming sources receive explicit
shard assignments and disable upstream splitters.

The explicit routes are `webdataset`, `lerobot_local`, and `robodm_container`.
Select one through `data.datasets[].backend`; none is a default or performance
winner. Before final review, workers=0 bounded runs completed for all three
routes, while the original workers=2 RoboDM run failed during spawn
serialization and cleanup. The integrated repair adds a focused two-worker,
two-epoch RoboDM test with observed worker IDs/PIDs, persistent PID reuse,
non-default prefetch, deterministic sample coverage, and clean child exit.
Backend-specific workers=2 Slurm reruns remain deferred.

Delivered batches expose configured/observed worker facts and the backend state
already supported by source contracts. RoboDM open/cache counters are visible;
LeRobot parquet/media counters and WebDataset cursor/handler state remain
bounded by their routes. Worker-process close counters are not sent after
process exit, so parent-observed clean exit is reported separately rather than
inventing telemetry. Decision: `NO_BACKEND_WINNER`.
