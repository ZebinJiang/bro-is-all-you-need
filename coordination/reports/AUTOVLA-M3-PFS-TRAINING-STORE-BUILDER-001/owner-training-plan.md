# Training Owner Plan Review: AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001

## Workspace Verification

- Owner: 20-OWNER · Training
- Mode: Wave 1 read-only plan gate; report-only write.
- Worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- `git branch --show-current`: `dev/feat-autovla-m3-dataloader-perf-harness`
- `git rev-parse HEAD`: `69c371e5861dccb6d374f8c1e155b55304a1f927`
- `git status --short --branch`: `## dev/feat-autovla-m3-dataloader-perf-harness...origin/dev/feat-autovla-m3-dataloader-perf-harness`
- Workspace check: PASS.
- Dispatch reasoning label: xhigh; prohibited higher mode not used.

## Evidence Reviewed

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `docs/architecture/DATALOADER_PERFORMANCE_HARNESS.md`
- `autovla/dataloader/perf/config.py`
- `autovla/dataloader/perf/metrics.py`
- `tests/dataloader/test_perf_harness.py`
- Current perf harness module inventory under `autovla/dataloader/perf/`

Task-card/spec traceability note: no task card or dedicated spec file for `AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001` was found under `coordination/`, `docs/`, or task-local `runs/tmp/` during read-only discovery. This review therefore uses the Manager dispatch plus the existing dataloader perf harness contract as the active plan-gate source.

## Training Hot-Path Relevance

The proposed PFS training-store read benchmark is directly relevant to future Training hot-path readiness. Before spending GPU allocation on real finetune, Training needs bounded evidence that the data read path can sustain deterministic batch-oriented reads without excessive latency, cache/path instability, or unsafe writes. This is especially useful because the existing perf harness already models training-facing metrics such as batch latency, data wait time, compute placeholder time, estimated GPU wait time, disk read throughput, cache hit rate, and missing telemetry.

The benchmark should be framed as a Training readiness proxy, not as training acceptance evidence. It can answer whether the storage and dataloader-facing layout are plausible enough for a later finetune dry-run plan. It cannot prove actual GPU utilization, optimizer behavior, model throughput, or end-to-end training convergence.

## PFS Training-Store Foundation

APPROVE as a foundation before real finetune, provided the implementation stays inside the existing dataloader perf-harness boundary:

- Add a narrow PFS/training-store benchmark mode or adapter path on top of the current `PerfBenchmarkConfig` / `PerfMetrics` / report surfaces.
- Keep reads bounded, deterministic, and reportable under `runs/`.
- Preserve the existing no-external-effect contract: no real model, tokenizer, checkpoint load, optimizer, W&B/HF network, full dataset conversion, dataset-root writes, or Slurm submission from the benchmark itself.
- Treat PFS results as storage/data-path evidence only; do not claim real finetune readiness without later compute-node training validation.
- Include explicit labels for cold/warm cache state, sample count, byte count when measurable, missing telemetry, and whether media decode was skipped or bounded.

The existing harness shape is appropriate because it already separates metadata-only, bounded-decode, and training-view concepts while recording missing GPU/CPU telemetry explicitly. A PFS training-store probe should extend that pattern rather than introduce a training loop.

## GPU-Wait And Data-Wait Proxy Interpretation

Without real training, GPU-wait/data-wait must be interpreted as a proxy:

- `data_wait_time_ms`, `compute_placeholder_time_ms`, and `data_to_compute_ratio` can indicate whether the dataloader/storage path is likely to starve a future compute loop.
- `estimated_gpu_wait_time_ms` can be useful for risk ranking, but it must remain an estimate derived from bounded data timing and placeholder compute assumptions.
- Missing GPU telemetry such as utilization, HBM bandwidth, and memory usage must remain explicit as `missing`, `not_observed`, or equivalent.
- PASS/WARN/FAIL thresholds should be described as PR #14 harness-readiness gates, not final finetune-performance gates.

Recommended interpretation:

- PASS means the bounded read path and report schema are stable enough to merge the harness and use it for later evidence collection.
- WARN means the benchmark is safe and useful but telemetry is incomplete, noisy, borderline, or lacks a baseline comparison.
- FAIL means safety or determinism boundaries are violated, required evidence is absent, or data-wait proxy indicates the storage path is not ready for downstream finetune planning.

## Safety Boundary

Training accepts the plan only with these hard boundaries:

- No real training loop.
- No real model, tokenizer, checkpoint, optimizer, or pretrained-weight access.
- No GPU/CUDA requirement for the benchmark itself.
- No W&B/HF network access.
- No Slurm submission from the PFS benchmark implementation.
- No full dataset conversion and no dataset-root mutation.
- No compatibility shim or `genesisvla` surface reintroduction.
- All generated reports, temp outputs, and benchmark evidence remain under governed `runs/` or task-local report paths.

## PR #14 PASS/WARN/FAIL Criteria

The PASS/WARN/FAIL criteria are acceptable for PR #14 readiness/merge if they are scoped to harness readiness:

- PASS: schema-valid reports are generated deterministically; all required safety flags are false; no writes occur outside the requested output directory; source dataset/PFS input remains read-only; missing GPU telemetry is explicit; bounded read counts and timing fields are present; no real training/model/external runtime is activated.
- WARN: GPU telemetry is missing by design; data-wait proxy is borderline; sample size is too small for strong performance claims; cache state is unknown; PFS variance is high; baseline comparison is absent; nevertheless the run remains safe and deterministic.
- FAIL: benchmark writes outside governed output paths; mutates input data; performs unbounded scans/conversions; loads model/checkpoint/tokenizer; touches network/W&B/HF; invokes Slurm; produces nondeterministic or schema-invalid reports; hides missing telemetry; or data-wait proxy clearly exceeds the merge-defined failure threshold.

Training recommends that WARN should not block PR #14 by itself when the warning is an honest telemetry limitation. FAIL should block merge until repaired.

## Recommended Implementation Plan

1. Extend the existing perf harness with a narrow PFS training-store read mode.
2. Add typed config fields only if necessary for a training-store root or manifest path; reject unsafe output paths and unknown fields consistently with existing config behavior.
3. Reuse `PerfMetrics` for throughput, latency, wait-ratio, and missing-telemetry reporting.
4. Add report fields that distinguish storage-read evidence from actual training evidence.
5. Add tests using tiny `tmp_path` fixtures only; do not depend on real PFS or external datasets.
6. Add negative tests for unsafe paths, external-effect strings, missing telemetry handling, and no writes outside output.
7. Document that real PFS performance validation, if needed, belongs in a later compute/HPC validation stage with explicit authorization.

## Validation Expectations

Login-node-safe validation for the implementation wave:

- `py_compile` for touched Python files.
- Focused pytest for the new perf-harness tests with tiny fixtures.
- Focused Ruff/Black on touched files.
- `git diff --check`.
- Scope scans for forbidden real-training/model/network/Slurm strings in new code paths.

Deferred validation:

- Real PFS read throughput, cache-state comparison, and compute-node timing should be gathered only in a later authorized validation stage.
- No real finetune or model execution should be used to validate this PR #14 harness tranche.

## Risks

- Proxy metrics may be over-interpreted as actual GPU starvation; reports must label them as estimates.
- PFS read measurements can be noisy due to shared filesystem cache and concurrent cluster load; reports should include sample counts and cache-state assumptions.
- Missing task-card/spec files reduce traceability; Manager should register or attach the formal task card/spec before final publication if this tranche proceeds beyond plan gate.
- If future validation requires actual PFS reads from large artifacts, Compute/Data should define explicit path, byte, sample, and node limits before execution.

## DevSpace MCP Compliance

DevSpace MCP, `vla-flywheel-devspace`, MCP connector tools, `open_workspace`, MCP read/write/edit/bash were not used.

## Subagent Retirement Ledger

- T-RO1 child subagent: none used.
- Retirement status: retired yes for this Owner-direct read-only plan review.

## Conclusion

APPROVE_PLAN
