# AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001 · Training RO1 Review

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `2322606f26fecbef37eafdb7504c848d476cd29e`
- `git status --short --branch`: branch matched; active task card is untracked as task-local governance input.

## Runtime Override Record

- requested model: `gpt-5.5`
- requested thinking: `high`
- no `thinking=max` used or required by this review.

## Evidence Reviewed

- `AGENTS.md`
- `boundaries.txt`
- `coordination/tasks/active/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001.yaml`
- `README.md`
- `docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md`
- `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V2.md`
- `docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md`
- `autovla/dataloader/perf/fair_native_loader_bakeoff.py`
- `tests/dataloader/test_fair_native_loader_bakeoff.py`
- relevant training dry-run references were checked for leakage context; no Training runtime execution was run.

## Training Relevance Assessment

The actual dataloader worker benchmark is relevant to future Training throughput work and should proceed as a pre-GPU200 evidence gate.

Current PR30 adapter-v1 evidence is explicitly diagnostic-only:

- `worker_count_label=configured_8`
- `actual_worker_count=not_measured`
- `multiprocessing_enabled=false`
- `prefetch_enabled=false`
- no GPU200 / Slurm / training run

That honesty is good, but it also means the adapter-v1 numbers are not enough to interpret future training-stage bottlenecks. A real worker benchmark is the correct next step because future Training needs evidence for whether the observed bottleneck is data decode, payload materialization, reader init, IPC/prefetch overhead, file open pressure, or Python worker orchestration.

## Leakage / Boundary Review

No leakage found in the reviewed plan and current candidate surfaces:

- no real training loop is authorized by the PR30 task card or README wording;
- no model, checkpoint, tokenizer, HF network, W&B service, endpoint, or robot behavior is authorized;
- current docs preserve `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`;
- current docs explicitly say adapter-v1 is diagnostic only and does not select a backend winner;
- `fair_native_loader_bakeoff.py` validates materialized RGB/action/state/action_mask payloads and rejects camera-ref-only payload comparisons;
- source dataset mutation is out of scope and protected.

## Training Metrics That Matter

For Training-stage bottleneck interpretation, the actual worker benchmark should report, per candidate and common sample window:

- actual worker count observed, not only configured worker label;
- multiprocessing enabled / prefetch enabled status;
- batch latency p50 / p95 / p99 and max;
- samples/s and frames/s;
- first-batch latency vs steady-state batch latency;
- reader init time and persistent-reader status;
- materialize payload time, batch read time, payload validation time, and report write time;
- file open count, bytes read, read MB/s, generated artifact size, generated file count;
- CPU user/system time, RSS max, and explicit missing metrics;
- cache hit/miss or equivalent reader reuse evidence;
- worker crash / timeout / exception count if any;
- explicit external-effect flags proving no model/checkpoint/tokenizer/HF/W&B/endpoint/robot side effects.

## Stop Conditions Before GPU200 Training

Training should not treat PR30 as a GPU200 training prerequisite until all of the following are true:

- actual worker count is measured and not left as `not_measured`;
- candidate rows are comparable on the same materialized payload contract and selected sample/window manifest;
- old invalidated camera-ref/preloaded-source rows are excluded from ranking;
- at least raw baseline plus intended converted candidates report actual-worker evidence or are explicitly fail-closed;
- docs preserve no-backend-winner / no-training-readiness wording unless Manager/user explicitly authorizes a later decision;
- generated datasets, logs, run outputs, and checkpoints remain untracked task-local evidence;
- Compute/HPC owns any real benchmark execution and records job/log/output evidence before Training interprets throughput.

## Findings

No Training-blocking leakage findings for this RO1 review.

Planning note: current adapter-v1 docs and tests still state `actual_worker_count=not_measured`. That is acceptable only because this task is explicitly to add/run the actual-worker benchmark next; it must not be published as actual worker evidence until replaced or supplemented by measured worker rows.

## DevSpace MCP Compliance

- DevSpace MCP used: no.

## Subagent Ledger

- child subagents used: none.
- retired: yes.

## Conclusion

APPROVE_TRAINING_RELEVANCE
