# Owner Compute/HPC Feasibility Plan

Task: `AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001`
Role: `80-OWNER · Compute/HPC`
Mode: read-only compute feasibility/planning plus report write only
Decision: `PLAN_ONLY_NO_COMPUTE_SUBMITTED`

## Dispatch and Workspace Verification

- User override recorded: `model=gpt-5.5`, `thinking=high`
- `thinking=xhigh` used: no
- `thinking=max` used: no
- DevSpace MCP used: no
- Worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- Git top level: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- Branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- HEAD: `f194b6e8d3d6679448749da36e6bfc68f690ef91`
- Slurm jobs submitted by this review: none
- GPU, CUDA, training, model load, checkpoint load, Hugging Face, W&B, endpoint, robot: not used
- Git stage/commit/push/PR/merge mutation: not performed
- Report-only write: `coordination/reports/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/owner-compute-plan.md`

## Interpreted Goal

Plan Compute/HPC routing for a native-adapter performance audit/optimization follow-up after PR #30 invalidation. The task forbids GPU200 training and Slurm GPU runs, but permits a fair native-loader rerun if Manager later authorizes execution. This report therefore separates lightweight local inspection from compute-allocation work and defines how future evidence should be recorded without mutating protected sources, readonly datasets, generated artifacts, or PR state.

## Affected Project Paths

- Runner: `autovla/dataloader/perf/fair_native_loader_bakeoff.py`
- Shared timing helpers: `autovla/dataloader/perf/native_loader_timing_v2.py`
- Tests/evidence expectations: `tests/dataloader/test_fair_native_loader_bakeoff.py`
- Prior fair rerun evidence root: `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001`
- Prior Compute/HPC approval: `coordination/reports/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/owner-compute.md`
- This task's future evidence root, if Manager authorizes execution:
  `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001`

## Current Runner and Evidence Expectations

- `FairNativeLoaderBakeoffConfig` requires positive bounded parameters and fail-closes unless `worker_count == 8`.
- The CLI entrypoint is `python -m autovla.dataloader.perf.fair_native_loader_bakeoff`.
- The runner writes `shared-sample-window-manifest.json`, `fair-native-loader-bakeoff.json`, `fair-native-loader-bakeoff.csv`, `fair-native-loader-bakeoff.md`, and `generated-artifact-ledger.json`.
- Candidate-level generated outputs are written under a working root, including `loader_contract.json`, `payload_validation.json`, `timing_result.json`, `timing_result.csv`, and `timing_result.md`.
- The current JSON schema contains `rows` and `schema_version`; each row records actual `worker_count`, but there is no separate `worker_count_label` field today.
- The conservative runner decision is `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY` when all four expected candidates are present.
- External-effect fields are expected to remain false: `checkpoint_read`, `model_load`, `real_training`, `hf_network`, `wandb`, `endpoint`, `robot`, and `tokenizer_load`.
- The generated-artifact ledger is expected to report `generated_artifacts_tracked=false`, `source_dataset_mutated=false`, and generated entries as ignored artifacts.

## Compute Policy

### Login/CPU-Local Allowed

Use the login node only for lightweight inspection, static checks, and already-generated evidence summarization. Suitable commands include:

- `pwd`
- `git rev-parse --show-toplevel`
- `git branch --show-current`
- `git rev-parse HEAD`
- `git status --short`
- `rg -n '<pattern>' <source-or-report-path>`
- `sed -n '<range>p' <source-or-report-path>`
- `find runs/tmp/<task-id> -maxdepth <n> -type f`
- `python -m autovla.dataloader.perf.fair_native_loader_bakeoff --help`
- `python -c '<read-only JSON summary>'` against existing `runs/tmp/**` evidence

Do not run the full fair benchmark on the login node. It materializes RGB payloads with ffmpeg, writes converted artifacts, and uses the bounded 8-worker timing path; that is too heavy and too writeful for login-node-only review.

### Compute Allocation Required

If Manager later authorizes a fresh fair native-loader rerun, route it to a Slurm compute allocation. Because this task forbids Slurm GPU runs, the rerun must be CPU-only:

- Use a CPU partition or CPU-only debug allocation approved by Manager/cluster policy.
- Do not request `--gres=gpu`, GPU200, A100 GPU resources, CUDA, or training resources.
- Do not reuse the prior `fair-native-loader-srun` wrapper as-is because it contains `--gres=gpu:1`.
- Do not fall back to a heavy login-node run if no CPU compute route is available; record `BLOCKED_COMPUTE_ROUTING_CPU_PARTITION_REQUIRED` instead.

Recommended future run envelope, only after Manager authorization:

```bash
srun -p <approved_cpu_partition> -c 32 --mem=128G --time=04:00:00 \
  bash runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/compute/run_fair_native_loader_inside_compute.sh
```

The exact partition must come from Manager/Slurm policy or discovery. This Owner should not invent a partition name.

## Allowed Commands For This Task Family

- Read-only source/report/evidence inspection commands listed above.
- CLI help inspection: `python -m autovla.dataloader.perf.fair_native_loader_bakeoff --help`.
- Existing-evidence JSON summarization using `python -c` without writing files.
- Future CPU-only fair native-loader rerun only if Manager explicitly authorizes execution and supplies/approves the compute route.
- Future task-local wrapper/report writes under `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/**` and `coordination/reports/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/**`, only if assigned by Manager.

## Forbidden Commands and Routes

- No GPU200 training.
- No `torchrun`, GR00T training bridge, model fine-tuning, checkpoint writing, or checkpoint loading.
- No Slurm GPU run, including `--gres=gpu`, A100/GPU200 partitions for this task, CUDA preflight, or GPU telemetry.
- No direct full fair-benchmark run on the login node.
- No writes to `datasets/readonly/**`.
- No generated artifact commit, including `runs/tmp/**`, `runs/slurm_debug/**`, `datasets/working/**`, benchmark payloads, converted parquet/tar/container outputs, checkpoints, or logs.
- No Hugging Face download/upload, W&B sync, endpoint, robot, or external service call.
- No source/tests/docs/PR mutation unless Manager issues a separate implementation packet.
- No `git add`, `git commit`, `git push`, PR edit, merge, reset, restore, clean, or stash from this Owner planning task.

## Evidence Paths For Future Execution

If Manager authorizes a CPU-only fair rerun, record:

- Wrapper command: `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/compute/srun_command.txt`
- CPU-only wrapper script: `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/compute/run_fair_native_loader_srun.sh`
- Inner script: `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/compute/run_fair_native_loader_inside_compute.sh`
- Exit status: `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/compute/fair-native-loader-srun.status`
- stdout/stderr log: `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/compute/fair-native-loader-srun.log`
- Benchmark JSON: `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/fair-benchmark/fair-native-loader-bakeoff.json`
- Benchmark CSV: `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/fair-benchmark/fair-native-loader-bakeoff.csv`
- Benchmark Markdown: `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/fair-benchmark/fair-native-loader-bakeoff.md`
- Shared sample/window manifest: `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/fair-benchmark/shared-sample-window-manifest.json`
- Generated artifact ledger: `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/fair-benchmark/generated-artifact-ledger.json`

Minimum evidence checks:

- status file equals `0`
- wrapper command has no `--gres=gpu`
- log contains `conclusion=NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY` unless optimization scope explicitly changes the decision contract
- JSON row count equals `4`
- every row has `status=RUNNABLE_NOW`, `payload_complete=true`, `missing_metrics=[]`
- every row has `worker_count=8`
- every external-effect flag is false
- ledger has `generated_artifacts_tracked=false` and `source_dataset_mutated=false`

## Worker Count Reporting

Current runner output has actual `worker_count` only. It does not emit `worker_count_label`.

Recommended reporting convention:

- Record `actual_worker_count` from `row["worker_count"]`.
- Record `worker_count_label` as a display-only string derived from the actual value, for example `workers=8`.
- Keep Slurm CPU allocation separate as `slurm_cpus_per_task`, for example `32`; never conflate `-c 32` with loader `worker_count=8`.
- If future output adds `worker_count_label`, validate it against `row["worker_count"]` and fail review if they disagree.
- For PR-visible summaries, prefer columns `worker_count_label` and `actual_worker_count`, or a single clear cell such as `workers=8 (actual)`.

## External Path and Dataset Policy

- Source dataset must remain read-only:
  `/home/cz-jzb/workspace/vla-flywheel/datasets/readonly/black-rubber-bellows-0622-0623-768-cmd-256-30hz`
- Converted/generated stores must remain under project-local `datasets/working/**`.
- Task outputs must remain under project-local `runs/tmp/**`.
- The current CLI requires `--gr00t-root`, but static inspection shows `gr00t_root` is only parsed/stored and not otherwise read by `fair_native_loader_bakeoff.py`. For a future rerun, prefer a project-local inert path under the task root unless Manager explicitly authorizes an external Isaac-GR00T17 path.

## Validation and Evidence Plan

1. Perform lightweight local verification of workspace, branch, HEAD, runner help, and existing evidence.
2. If existing PR30 fair evidence is sufficient, summarize it without rerun.
3. If Manager requests a fresh rerun, request or confirm CPU-only Slurm routing first.
4. Generate a task-local CPU-only wrapper with no GPU flags and a logged raw `srun` command.
5. Run only the fair native-loader benchmark through the CPU compute allocation.
6. Summarize JSON rows, external-effect flags, status/log conclusion, generated-artifact ledger, and git-ignore status.
7. Report whether optimization changes are feasible without training/GPU and whether a separate implementation packet is needed.

## Risks and Recovery

- Risk: using the prior GPU wrapper would violate this task. Recovery: require CPU-only route and block if unavailable.
- Risk: running full fair benchmark on login can overload login resources. Recovery: classify as compute-required and do not run locally.
- Risk: generated payload artifacts are large and tempting to stage. Recovery: keep outputs under `runs/tmp/**` and `datasets/working/**`, verify with `git status --short` and `git check-ignore -v`, and never stage generated evidence.
- Risk: `worker_count_label` could drift from actual worker count. Recovery: derive labels from row `worker_count` and report Slurm CPUs separately.
- Risk: required CPU partition is unknown. Recovery: request Manager compute routing or Slurm environment discovery; do not guess and do not use GPU partition as fallback.

## DevSpace MCP Compliance

DevSpace MCP was not used. All inspection was local-shell read-only plus this report write.

## Subagent Ledger

- Subagents used: none
- Child-agent depth: `0`
- Retirement status: not applicable
