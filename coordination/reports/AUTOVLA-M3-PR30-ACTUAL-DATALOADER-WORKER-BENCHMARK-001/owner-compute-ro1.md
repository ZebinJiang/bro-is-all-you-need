# Owner Compute/HPC RO1 Plan

Task: `AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001`
Role: `80-OWNER · Compute/HPC`
Mode: Compute-RO1 read-only compute plan plus this report write only
Conclusion: `APPROVE_COMPUTE_PLAN`

## Model and Dispatch Override

- User override recorded: `model=gpt-5.5`, `thinking=high`
- `thinking=xhigh` used: no
- `thinking=max` used: no
- DevSpace MCP used: no
- Subagents used: none
- Child-agent depth: `0`
- Subagent retirement status: not applicable

## Workspace Verification

- Worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- Branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- Expected starting HEAD: `2322606f26fecbef37eafdb7504c848d476cd29e`
- Observed HEAD: `2322606f26fecbef37eafdb7504c848d476cd29e`
- Current git status observed: untracked task YAML/report path only at this RO1 checkpoint
- Slurm submitted by this Owner turn: no
- Source/tests/docs/PR mutation by this Owner turn: no
- Git stage/commit/push/PR/merge mutation by this Owner turn: no
- Report-only write: `coordination/reports/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/owner-compute-ro1.md`

## Required Inputs Read

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/COMPUTE_EXECUTION_GOVERNANCE.md`
- `coordination/tasks/active/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001.yaml`
- `docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md`
- `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V2.md`

## Interpreted Goal

Define the compute-node benchmark plan and safety envelope for an actual dataloader/native-loader worker benchmark that replaces prior configured-worker labels with measured worker evidence. This RO1 turn does not authorize execution; it prepares the safe compute route for a later Manager-authorized execute wave.

## Current Feasibility Notes

- The current PR30 V2 docs correctly classify adapter-v1 numbers as diagnostic-only, not GPU200 evidence, not Slurm evidence, not a final backend winner, and not training-readiness evidence.
- Current `fair_native_loader_bakeoff.py` records `worker_count_label=configured_8` and `actual_worker_count=not_measured`.
- Current `fair_native_loader_bakeoff.py` and `native_loader_timing_v2.py` fail-close unless `worker_count == 8`.
- Therefore, the default `0,2,4,8` matrix must not be launched against the current runner as-is. Data must first implement a matrix-capable actual-worker benchmark runner and actual worker instrumentation.
- Once implemented, the benchmark is compute-required because it performs bounded dataset reads/materialization/timing across multiple worker counts and candidates. It is not a login-node workload.

## Compute Policy

### Login Node

Allowed on login node:

- File inspection, `rg`, `sed`, `find`, and JSON/YAML parsing.
- CLI help or syntax checks only if they do not materialize datasets or run timing loops.
- Static verification that runner arguments, output schema, and report paths exist.

Forbidden on login node:

- Full actual-worker benchmark.
- Dataset conversion/materialization timing loops.
- Multi-candidate timing matrix.
- Long pytest/validation suites, package builds, training, inference, or any heavy CPU/IO workload.

### Compute Node

The actual dataloader worker benchmark requires a Manager-authorized compute-node allocation before execution. The run must use project/task-local wrappers that log the equivalent raw command, execution environment, and output roots.

The benchmark should use CPU resources only. GPU is unnecessary because the scope is dataloader/native-loader worker behavior, CPU multiprocessing, file IO, ffmpeg/materialization overhead, and adapter/reader timing. No model forward pass, training step, CUDA kernel, GPU memory telemetry, or GPU200 behavior is in scope.

Do not request GPU solely for monitoring. GPU monitoring would consume scarce GPU resources, create misleading GPU-adjacent evidence, and violate the no-GPU/no-training intent without adding value to worker-count validation. Use CPU, memory, process, IO, and Slurm node/job metadata instead.

## Resource Request Envelope

Proposed resource class for Manager approval:

- execution location: Slurm compute node
- partition/account/QoS: must come from Manager-approved Slurm config or explicit compute routing; do not invent
- nodes: `1`
- tasks: `1`
- CPUs per task: `32`
- memory: `128G`
- wall time: `06:00:00` for the default matrix
- GPU: none
- CUDA visible devices: empty/disabled
- working root: `datasets/working/autovla_actual_worker_bakeoff_v1`
- output root: `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/actual-worker-benchmark`

If CPU partition, account, QoS, wrapper path, project environment, or writable output roots are missing, stop as `BLOCKED_COMPUTE_ENV` rather than falling back to login-node execution or GPU resources.

## Benchmark Matrix

Default matrix:

- `worker_count`: `0,2,4,8`
- `batch_size`: `8`
- `measured_batches`: `100`
- `warmup_batches`: `10`
- `repeats`: `3`
- `max_samples`: `4096`
- `max_episodes`: `32`
- candidates: mandatory D1 through D5 from the Data task implementation; optional D6 only if already implemented and in-scope

Default matrix acceptance requires every mandatory candidate to run every worker count or emit a fail-closed per-row status that clearly distinguishes dependency/implementation failure from performance.

Fallback matrix, only if compute budget is constrained and Manager explicitly approves before execution:

- Preferred fallback: `worker_count=0,4,8`, `batch_size=8`, `measured_batches=50`, `warmup_batches=5`, `repeats=2`, `max_samples=2048`, `max_episodes=16`
- Severe fallback: `worker_count=0,8`, `batch_size=8`, `measured_batches=30`, `warmup_batches=5`, `repeats=2`, `max_samples=1024`, `max_episodes=8`

Fallback requirements:

- Record `FALLBACK_MATRIX_APPROVED_BY_MANAGER` with exact approving packet or steering note.
- Preserve worker-count endpoints `0` and `8`.
- State that fallback evidence is diagnostic only and may not support scaling conclusions across intermediate worker counts.
- Do not silently substitute fallback values in docs, tables, or PR text.

## Command Shape

The exact module name may be finalized by the Data implementation, but the command shape should be:

```bash
export PYTHONUNBUFFERED=1
export PYTHONNOUSERSITE=1
export CUDA_VISIBLE_DEVICES=
export NVIDIA_VISIBLE_DEVICES=
export WANDB_DISABLED=true
export WANDB_MODE=disabled
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python \
  -m autovla.dataloader.perf.actual_dataloader_worker_bakeoff \
  --source-dataset /home/cz-jzb/workspace/vla-flywheel/datasets/readonly/black-rubber-bellows-0622-0623-768-cmd-256-30hz \
  --working-root /home/cz-jzb/workspace/vla-flywheel/datasets/working/autovla_actual_worker_bakeoff_v1 \
  --output-dir /home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff/runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/actual-worker-benchmark \
  --worker-counts 0,2,4,8 \
  --batch-size 8 \
  --warmup-batches 10 \
  --measured-batches 100 \
  --repeats 3 \
  --max-episodes 32 \
  --max-samples 4096 \
  --seed 11
```

Wrapper shape, only after Manager execution authorization:

```bash
srun -p <approved_cpu_partition> -N 1 -n 1 -c 32 --mem=128G --time=06:00:00 \
  bash runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/compute/run_actual_worker_benchmark_inside_compute.sh
```

The wrapper must emit the equivalent raw `srun` command to a task-local evidence file before execution. No `--gres=gpu`, GPU partition, CUDA preflight, model/training command, HF/W&B network call, endpoint, or robot command is allowed.

## Required Job Evidence

Required metadata files under `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/compute/`:

- `srun_command.txt`
- `run_actual_worker_benchmark_srun.sh`
- `run_actual_worker_benchmark_inside_compute.sh`
- `actual-worker-benchmark-srun.status`
- `actual-worker-benchmark-srun.stdout.log`
- `actual-worker-benchmark-srun.stderr.log`
- `environment.json`
- `job_metadata.json`

`job_metadata.json` must include:

- Slurm job id from `SLURM_JOB_ID`
- node list from `SLURM_JOB_NODELIST`
- hostname from `hostname`
- cwd from `pwd`
- git root
- branch
- commit SHA
- dirty status summary
- Python executable and version
- start/end timestamps
- exit code
- output root
- working root
- exact resource request
- explicit `gpu_requested=false`
- explicit `training_used=false`
- explicit `model_checkpoint_tokenizer_used=false`
- explicit `hf_wandb_endpoint_robot_used=false`

Required benchmark outputs under `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/actual-worker-benchmark/`:

- result JSON with one row per candidate and worker count
- CSV/Markdown summary tables
- actual worker evidence JSONL or equivalent per worker-count row
- generated artifact ledger
- shared sample/window manifest
- backend decision status preserving no final winner unless all fairness gates explicitly approve a stronger state

## Actual Worker Count Verification

Rows must separate configuration from evidence:

- `requested_worker_count`
- `worker_count_label`
- `actual_worker_count`
- `actual_worker_count_source`
- `worker_pids`
- `unique_worker_pid_count`
- `worker_init_events`
- `worker_sample_events`
- `multiprocessing_enabled`
- `prefetch_enabled`
- `persistent_workers`
- `prefetch_factor`
- `dataloader_start_method`
- `worker_count_status`

Expected semantics:

- For `worker_count=0`, `actual_worker_count=0`, no child worker PIDs, `multiprocessing_enabled=false`, and row status can pass only if in-process iteration is explicitly recorded.
- For `worker_count>0`, `actual_worker_count` must equal `requested_worker_count`, `unique_worker_pid_count` must equal `requested_worker_count`, and every worker PID must emit at least one init or sample event.
- A configured label such as `configured_8` is not evidence. It may appear only as `worker_count_label`.
- Missing worker PIDs, mismatched counts, no worker activity, or process-introspection failure must produce a fail-closed row status such as `BLOCKED_WORKER_EVIDENCE` or `ATTEMPTED_FAIL_WORKER_COUNT_MISMATCH`, not a passing performance row.
- The benchmark must record whether each timing row includes warmup-only or measured batches and must never mix warmup latency into measured metrics.

## Safety Envelope

Forbidden:

- GPU200, GPU allocation, `--gres=gpu`, CUDA requirement, or GPU monitoring as a substitute for CPU worker evidence.
- Real training, fine-tuning, `torchrun`, GR00T training bridge, model load, checkpoint read/write, tokenizer load, HF network, W&B, endpoint, or robot behavior.
- Writes to `datasets/readonly/**`.
- Generated artifact commits.
- Output outside `runs/tmp/**` and `datasets/working/**`.
- PR ready/merge/final backend winner decision from this compute benchmark alone.

Required:

- Source dataset read-only.
- Generated working data under `datasets/working/autovla_actual_worker_bakeoff_v1/**`.
- Runtime evidence under `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/**`.
- Generated artifact ledger with `generated_artifacts_tracked=false` and `source_dataset_mutated=false`.
- Docs must preserve diagnostic/no-final-winner wording unless a later Manager packet explicitly changes publication semantics.

## Stop Conditions

Record `BLOCKED_COMPUTE_ENV` and stop before execution if any of these occur:

- Worktree, branch, or HEAD does not match the task packet.
- Matrix-capable runner is missing or still rejects `worker_count` values `0`, `2`, or `4`.
- Actual worker instrumentation fields are missing from the output schema.
- Project-local Python environment is missing or cannot import required packages.
- CPU-only Slurm route, partition, account, wrapper, or writable evidence path is unavailable.
- Scheduler rejects the CPU-only job for environment/resource reasons.
- Job starts without a Slurm job id, hostname, cwd, git commit, log path, or exit-code evidence.
- Output root or working root cannot be written under governed paths.
- Source dataset path is missing or any code attempts to mutate `datasets/readonly/**`.
- Generated artifact ledger is missing.
- Disk capacity is insufficient for generated working artifacts.

Record `BLOCKED_COMPUTE_POLICY` and stop if any route requires GPU resources, scheduler-policy bypass, raw unwrapped Slurm submission, accounting/cgroup evasion, cluster config mutation, or broader resources than Manager authorized.

Record `FAIL` only for an executed, authorized benchmark whose environment and policy were valid but whose benchmark logic or outputs are internally invalid in a non-recoverable way.

## Validation and Reporting Plan

1. Manager/Data implements or confirms a matrix-capable actual-worker benchmark runner.
2. Compute/HPC rereads the final runner interface before execution.
3. Manager authorizes a CPU-only Slurm execute packet with exact partition/account/QoS/walltime.
4. Execute through task-local wrapper only.
5. Verify job metadata and logs.
6. Summarize all candidate/worker-count rows.
7. Verify actual worker evidence and external-effect flags.
8. Verify generated artifacts remain ignored and untracked.
9. Write Compute/HPC execution review with `APPROVE_COMPUTE`, `BLOCKED_COMPUTE_ENV`, `BLOCKED_COMPUTE_POLICY`, or `FAIL` as applicable.

## Risks and Recovery

- Risk: current PR30 runner supports only configured worker label `8`. Recovery: block execution until Data implements the actual-worker matrix.
- Risk: login-node saturation. Recovery: keep login work to inspection and route actual benchmark to compute.
- Risk: GPU accidentally requested through a reused wrapper. Recovery: require explicit no-GPU wrapper evidence and reject any `--gres=gpu`.
- Risk: configured worker label is mistaken for measured worker count. Recovery: require worker PID/event evidence and fail closed on mismatch.
- Risk: generated artifacts are staged. Recovery: keep under governed ignored roots and require `git ls-files runs/tmp datasets/working datasets/readonly checkpoints` plus `git status --short --ignored` checks before publication.

## Final Decision

`APPROVE_COMPUTE_PLAN`

The compute-node benchmark plan is approved as a plan only. Execution must wait for Manager authorization, Data implementation of actual worker-count instrumentation, a CPU-only Slurm route, and the evidence requirements above.
