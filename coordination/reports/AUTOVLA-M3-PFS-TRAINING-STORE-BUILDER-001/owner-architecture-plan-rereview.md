# AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001 Architecture Plan Rereview

Role: 10-OWNER - Architecture
Mode: Wave 1 narrow read-only rereview plus this Owner report write
Dispatch reasoning policy: thinking=xhigh requested; thinking=max not used

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- `git branch --show-current`: `dev/feat-autovla-m3-dataloader-perf-harness`
- `git rev-parse HEAD`: `69c371e5861dccb6d374f8c1e155b55304a1f927`
- `git status --short --branch`:
  - `## dev/feat-autovla-m3-dataloader-perf-harness...origin/dev/feat-autovla-m3-dataloader-perf-harness`
  - untracked report/task evidence only: `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/` and `coordination/tasks/active/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001.yaml`

Workspace verification: PASS.

## Reconciled Evidence Reviewed

- Active task card now present in PR #14 worktree:
  - `coordination/tasks/active/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001.yaml`
- Normative spec read from root-checkout path, without copying or mutating `.agent-docs` in the PR #14 worktree:
  - `/home/cz-jzb/workspace/vla-flywheel/.agent-docs/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-SPEC.md`
- Prior Architecture blocked plan:
  - `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-architecture-plan.md`
- Current perf module guide:
  - `autovla/dataloader/perf/MODULE.md`

The prior `BLOCKED_SCOPE` was caused by missing task/spec evidence. Manager reconciliation resolves that blocker.

## Architecture Boundary Assessment

Architecture approves the plan boundary for a PFS-backed AutoVLA Training Store v0 builder inside PR #14 scope.

The active task card and normative spec now define:

- PFS-backed Training Store as the optimization target, not local NVMe staging or a node-local cache.
- Required modes: `store-plan`, `store-build-bounded`, and `store-read-benchmark`.
- Required outputs: `training_store_manifest.json`, `sample_index.jsonl`, `episode_index.jsonl`, `shards/*.npz`, `stats/action_statistics.json`, `checksums.json`, `build_report.json`, and `read_benchmark_report.json`.
- Bounded evidence location under `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/**`.
- No writes into `datasets/readonly`.
- No committed media/store artifacts.
- No dependency spec change.
- No `genesisvla` compatibility shim.
- No real training, finetune, model/checkpoint/tokenizer load, checkpoint download, full dataset conversion, full media predecode, W&B/HF network, endpoint, or robot surface.

The plan is compatible with the current `autovla.dataloader.perf` package. Existing `metadata-only`, `bounded-decode`, and `training-view` behavior can be extended additively without changing M1/M2 public contracts, Model contracts, or Training contracts.

## API And Artifact Recommendation

Approved implementation shape:

- Add Training Store v0 contracts under `autovla/dataloader/perf/`, with `training_store.py` and `io_metrics.py` acceptable.
- Extend the existing perf CLI mode contract rather than creating a parallel runtime entry point.
- Keep `PFS` as the public storage backend wording: `storage_backend: pfs_shared`, `local_stage_used: false`.
- Treat local cache/staging as explicitly unavailable for this environment and not part of the public Training Store contract.
- Use deterministic, versioned manifest/index/shard/checksum schemas.
- Include dataset artifact fingerprint, transform fingerprint, statistics fingerprint, source format, adapter name/version, bounded build parameters, shard checksums, and explicit external-effect booleans in the manifest.
- Preserve sample source/provenance and action/state/mask shape information in the sample index.
- Keep `.npz` shards as bounded task evidence only; do not commit generated store payloads.

## Scope Guardrails For Implementation

Implementation may proceed inside the current PR #14 scope if it stays within:

- `autovla/dataloader/**`
- `tests/dataloader/**`
- `tests/meta/**`
- focused docs/examples/configs required by the task card
- task reports/evidence under the authorized paths

Do not change dependency specs, Model/Training public APIs, `autovla/core` contracts, `genesisvla/**`, model/checkpoint/runtime paths, PR/base branch state, or completion-state fields.

Compute-node benchmark execution and any raw `srun`/wrapper policy details should be reviewed by Compute/HPC and Quality before execution. Architecture approval here covers the PFS Training Store artifact/API boundary, not independent authorization to run compute jobs.

## Plan Gate Decision

- PFS artifact/API boundary: APPROVED.
- PFS-backed store vs local cache wording: APPROVED; PFS is authoritative, local cache is not public contract.
- Store manifest/index/shard contract: APPROVED as v0, with deterministic schema/version/checksum/fingerprint requirements.
- M1/M2/Model/Training contract drift: none required by the plan.
- `genesisvla` shim: not allowed and not needed.
- PR #14 scope: implementation can proceed as a bounded continuation of the dataloader perf harness.

## DevSpace MCP Compliance

DevSpace MCP: no. No `vla-flywheel-devspace`, MCP connector, `open_workspace`, or MCP read/write/edit/bash was used as workflow or evidence.

## Subagent Ledger

Child subagents: none used.
Retired: yes.

## Conclusion

APPROVE_PLAN
