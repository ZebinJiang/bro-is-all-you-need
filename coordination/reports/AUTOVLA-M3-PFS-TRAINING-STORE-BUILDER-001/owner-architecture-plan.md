# AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001 Architecture Plan Gate

Role: 10-OWNER - Architecture
Mode: Wave 1 read-only plan gate plus this Owner report write
Dispatch reasoning policy: thinking=xhigh requested; thinking=max not used

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- `git branch --show-current`: `dev/feat-autovla-m3-dataloader-perf-harness`
- `git rev-parse HEAD`: `69c371e5861dccb6d374f8c1e155b55304a1f927`
- `git status --short --branch`: `## dev/feat-autovla-m3-dataloader-perf-harness...origin/dev/feat-autovla-m3-dataloader-perf-harness`

Workspace verification: PASS.

## Required Evidence Status

Required dispatch inputs were checked:

- `AGENTS.md`: read.
- `boundaries.txt`: read.
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`: read.
- `coordination/tasks/active/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001.yaml`: **missing**.
- `.agent-docs/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-SPEC.md`: **missing**.

Narrow filename lookup for `AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER`, `TRAINING-STORE`, and `PFS` under the worktree found no replacement task/spec source. Because the task card and spec are the contract authority for this plan gate, Architecture cannot approve implementation yet.

## Existing Perf Surface Reviewed

Reviewed current dataloader perf implementation and tests:

- `autovla/dataloader/perf/config.py`
- `autovla/dataloader/perf/benchmark.py`
- `autovla/dataloader/perf/metrics.py`
- `autovla/dataloader/perf/report.py`
- `tests/dataloader/test_perf_harness.py`

Current perf harness observations:

- `PerfBenchmarkConfig` is bounded and rejects output under the dataset root.
- Modes are explicit: `metadata-only`, `bounded-decode`, and `training-view`.
- `bounded-decode` is compute-context gated.
- `run_benchmark()` records no model, checkpoint, real training, HF, W&B, Slurm submission, or dataset write side effects.
- `PerfMetrics` and `PerfClassification` keep missing telemetry explicit.
- `build_fast_training_view_schema()` is a schema sketch only; it does not define or build a PFS-backed Training Store artifact.

This is a reasonable foundation for a future store builder, but it is not itself a sufficient PFS Training Store contract.

## Architecture Plan Assessment

The likely safe implementation direction, once the missing task/spec are restored, is:

- Add an additive Training Store artifact surface under `autovla/dataloader/perf/` or another Data-owned `autovla/dataloader` submodule approved by the task card.
- Treat PFS as the authoritative shared backing store for immutable training-view artifacts, indexes, and shards.
- Treat local cache/NVMe wording as ephemeral staging only, not the source of truth and not a required publication artifact.
- Define a stable manifest/index/shard contract with schema version, dataset artifact fingerprint, transform/statistics fingerprints, shard ids, checksum fields, sample/episode index references, size/count metadata, and generation policy.
- Keep store-building dry-run or manifest-only unless the task explicitly authorizes materializing shards.
- Preserve `datasets/readonly` immutability and route generated store artifacts to governed `datasets/working`, `datasets/cache`, or task-approved output paths.
- Keep report/evidence outputs under `runs/`, not inside package source.
- Do not touch Model/Training public contracts, `autovla/core`, dependency specs, `genesisvla` shims, real model/training/runtime code, Slurm submission, GPU/CUDA, W&B/HF network, endpoint, or robot surfaces.

## Review Focus Decisions

- Training Store artifact boundary and API shape: not approvable until the missing spec defines artifact ownership, output path policy, and materialization level.
- PFS-backed store vs local cache wording: should be PFS authoritative, local cache ephemeral/staging only.
- Store manifest/index/shard contract: should be versioned, checksum/fingerprint based, immutable-by-contract, and deterministic; exact fields require the missing spec.
- M1/M2/Model/Training public contract drift: current inspected perf surface does not show drift; future work should remain additive under Data/perf.
- `genesisvla` compatibility shim: none needed and must remain forbidden.
- Current PR #14 scope: implementation should not proceed until task card and spec are present or Manager supplies an equivalent authoritative scope artifact.

## Validation Plan For A-W1 Once Unblocked

Recommended focused validation after implementation:

- Project-local Python syntax check for touched Python files.
- Focused pytest for Training Store builder tests and existing `tests/dataloader/test_perf_harness.py`.
- Ruff/Black on touched Python files.
- `git diff --check`.
- Static scan proving no dependency file, `genesisvla/**`, Model/Training runtime, Slurm submission, W&B/HF network, checkpoint/model-weight, dataset-payload, or endpoint/robot scope was introduced.

No heavy validation, Slurm, GPU, real training, full dataset conversion, or external runtime should run during this plan gate.

## Risks And Rollback Notes

- Main blocker: missing task card and spec prevent Architecture from verifying the exact public contract and write scope.
- Design risk: ambiguous PFS/local-cache wording could accidentally make ephemeral local cache a public artifact. The spec should fail closed on that wording.
- Data movement risk: store builder must avoid per-run full dataset copies and avoid writing under `datasets/readonly`.
- Rollback: because the proposed work should be additive, rollback should be limited to removing the new Training Store module/tests/docs and exports.

## DevSpace MCP Compliance

DevSpace MCP: no. No `vla-flywheel-devspace`, MCP connector, `open_workspace`, or MCP read/write/edit/bash was used as workflow or evidence.

## Subagent Ledger

Child subagents: none used.
Retired: yes.

## Conclusion

BLOCKED_SCOPE
