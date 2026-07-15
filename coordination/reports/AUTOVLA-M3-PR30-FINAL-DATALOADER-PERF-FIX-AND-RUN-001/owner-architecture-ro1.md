# AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001 · Owner Architecture RO1

## Workspace verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- HEAD: `882b24af518fe1676fdb5430e52d3877d018084a`
- required HEAD: `882b24af518fe1676fdb5430e52d3877d018084a`
- workspace_check: PASS

## Evidence reviewed

- Task card: `coordination/tasks/active/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001.yaml`
- Current PR30 benchmark/source surfaces under `autovla/dataloader/perf/**`
- Current candidate reader/store surfaces under `autovla/dataloader/stores/**`
- Current benchmark docs and README surfaces.
- Existing actual-worker tests under `tests/dataloader/test_actual_dataloader_worker_bakeoff.py`
- Protected-path diff scan for dependency/tooling surfaces.

## Decision

Conclusion: APPROVE_BOUNDARY_AFTER_DATA_FIXES

The Architecture boundary is approved for Data-owned fixes and a subsequent Compute/HPC run, not for immediate final PASS. The actual-worker benchmark belongs under `autovla/dataloader/perf`; data-only adapter/store fixes belong under `autovla/dataloader/stores` when needed for fair candidate behavior. No dependency, pyproject, requirements, training, model, checkpoint, tokenizer, endpoint, robot, or PR-ready/merge scope is authorized.

## Fairness blockers

- D1/D1a may be called GR00T/LeRobot native only with a real data-only native route and no model/checkpoint/tokenizer/training/HF/network/runtime side effect.
- If D1/D1a is unsafe or unavailable, it must remain not-run/blocked; the runnable v2.1 path must be labeled as the AutoVLA v2.1 adapter row, not native GR00T/LeRobot.
- D6 is optional; if absent, retain `NOT_IMPLEMENTED_IN_CURRENT_PR`.
- No backend winner may be selected unless mandatory comparability gates pass: same manifest, complete payloads, actual worker evidence, no blocking missing telemetry, and comparable timing rows.
- Adapter-v1 diagnostic history must stay diagnostic-only.

## Allowed Data-W1 write scope

- `autovla/dataloader/perf/**`
- `autovla/dataloader/stores/**`
- `tests/dataloader/**`
- `tests/meta/**` only for policy/publication guardrails
- `README.md`
- `docs/benchmarks/PR30_FINAL_DATALOADER_PERFORMANCE.md`
- `docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md`
- `docs/benchmarks/PR30_RESULT_CONSISTENCY_AUDIT.md`
- `docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md`
- `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V2.md`
- task-local reports/evidence under the allowed task paths.

Protected: `datasets/readonly/**`, checkpoints/model weights, `pyproject.toml`, `requirements/**`, `Makefile`, `.github/**`, `AGENTS.md`, `code-input/**`, dependencies, PR ready/merge, generated artifact commit.

## Required tests

- Candidate label policy tests for D1/D1a and AutoVLA v2.1 adapter row.
- Same-manifest and actual-worker evidence tests.
- D6 optional-not-implemented and no-winner decision tests.
- Store adapter regression tests for deterministic ordering, path containment, payload completeness, and no source mutation.
- Docs/publication guardrail tests if ignored benchmark docs are linked from tracked docs.

## Documentation guardrails

- Keep PR #30 in draft/request-changes posture unless final fairness gates pass.
- State D1/D6 limitations plainly.
- Do not claim final backend winner, training backend, fine-tune readiness, model quality, GPU200 training, endpoint, robot, or deployment readiness.
- Force-add ignored benchmark docs only with explicit narrow pathspecs if they are intended to be PR-visible.

## DevSpace MCP compliance

DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash were not used.

## Runtime override

User override recorded: model `gpt-5.5`, thinking `high`; no `xhigh` or `max` used.

## Subagent ledger

- Child subagents used: none.
- Review mode: direct read-only Architecture RO1.
- retired: yes.
