# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 Owner Compute/HPC Plan

## Workspace Verification

- role: `80-OWNER · Compute/HPC`
- mode: read-only planning plus owner report only
- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- HEAD: `3573930421a2f9be66b222d602db680a77aadf3f`
- expected branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- expected HEAD: `3573930421a2f9be66b222d602db680a77aadf3f`
- workspace check: PASS
- git status: untracked planning surfaces only under `coordination/reports/...` and `coordination/tasks/active/...`
- note: shell emitted `whoami: cannot find name for user ID 2000`; repository evidence remained usable.

## Evidence Reviewed

- owner packet:
  `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-packets/compute-plan.md`
- task card:
  `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
- compute governance:
  - `docs/coordination/COMPUTE_EXECUTION_GOVERNANCE.md`
  - `coordination/COMPUTE_EXECUTION_STATE.yaml`
  - `.agent-docs/slurm_sandbox_policy.md`
  - `.agent-docs/slurm_environment_discovery.md`
- project Slurm wrappers/config:
  - `scripts/slurm/request_compute_debug.sh`
  - `scripts/slurm/submit_sandbox_job.sh`
  - `configs/slurm/default_sandbox.json`
  - `configs/slurm/debug_profiles.json`
- current benchmark/runtime surfaces:
  - `autovla/dataloader/perf/config.py`
  - `autovla/dataloader/perf/benchmark.py`
  - `autovla/dataloader/perf/training_store.py`
  - `autovla/training/slurm_harness.py`
- neighboring owner evidence reused for bounded telemetry intent:
  - `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-plan.md`

## Compute Position

Planning is feasible and the compute split is clear enough to proceed without changing scheduler policy or widening scope. This task should remain a governed two-class execution plan:

- login node for static planning, config validation, path checks, `git diff --check`, JSON/YAML parsing, wrapper dry-run rendering, and other lightweight command generation only;
- compute-node CPU work for real store benchmark/build/read passes that touch bounded dataset windows or candidate-store I/O;
- compute-node GPU work for the real GR00T-N1D6 bounded 1-GPU 200-step telemetry tranche only.

Anything beyond those classes, especially long training, distributed runs, multi-GPU scaling, raw scheduler bypass, or dataset-wide conversion outside bounded policy, would leave the approved task envelope.

## Login-Node vs Compute-Node Split

The current repo policy already classifies this correctly:

- login-node safe:
  - planning and report writing
  - config/schema/path validation
  - wrapper `--dry-run`
  - syntax/drift/diff checks
- compute-node required:
  - `bounded-decode` benchmark mode
  - store build/read benchmark modes under `autovla/dataloader/perf/config.py`
  - any candidate-store build that writes governed benchmark artifacts
  - the real 1-GPU 200-step telemetry run

The benchmark code already enforces part of this boundary: `bounded-decode` refuses to run unless a compute context is present. The task card also explicitly names `real compute-node store benchmark` and `real 1-GPU 200-step telemetry on runnable candidates`, so pushing those onto the login node would violate both code intent and governance.

## Job Shape Recommendation

The suggested `srun` pattern should not become the primary execution surface for the milestone. Use it only for one short sequential preflight allocation when environment validation on a compute node is genuinely needed.

Recommended shape:

- one optional short `srun` debug/preflight allocation:
  - verify the compute environment, dataset mount visibility, local checkpoint visibility, and command startup behavior
  - no final benchmark evidence should depend on repeated interactive `srun` sessions
- one formal CPU-class sequential benchmark job:
  - run the bounded store benchmark workflow across the candidate set in one controlled order using the shared deterministic sample/window manifest
  - keep this job GPU-free
- separate formal 1-GPU telemetry jobs for runnable candidates:
  - one job per runnable candidate is preferred over folding multiple candidates into one long GPU job
  - this gives cleaner per-candidate evidence, simpler failure isolation, and avoids wasting completed candidate telemetry if one candidate fails late

So the answer is: not one all-purpose sequential `srun` session, and not a single mixed CPU+GPU monolith. Use multiple formal jobs by resource class, with an optional single `srun` preflight only.

## Resource Reasonableness

The task’s intended resource posture is reasonable if kept bounded:

- store benchmark:
  - CPU-only
  - one node, one task, modest memory/CPU, no `gres`
  - sequential candidate execution is appropriate because the value is comparative consistency, not wall-clock parallelism
- 200-step telemetry:
  - exactly 1 GPU per runnable candidate
  - bounded 200-step budget only
  - enough host CPU and memory to keep the loader from becoming the artificial bottleneck

Current repo signals:

- `configs/slurm/default_sandbox.json` is filled and usable for formal CPU-class submission on `cz_hpc01` / `a100`, but it is explicitly minimal and GPU-free (`gres: none`, `cpus_per_task: 1`, `mem: 4G`)
- `configs/slurm/debug_profiles.json` contains a prefilled `h800-gpu` debug shape (`16 CPU`, `64G`, `gpu:1`, `01:00:00`) that is reasonable as an upper-bound interactive preflight shape for the telemetry tranche

Compute/HPC recommendation:

- do not reuse the minimal CPU-only default sandbox config for the final telemetry submission
- do not invent the final GPU partition/QoS/account in the report
- require the implementation to provide a task-specific GPU-capable wrapper/config path for the telemetry jobs, sourced from explicit task config rather than guessed defaults

## Legitimate `BLOCKED_COMPUTE_ENV` Conditions Before Execution Starts

The following are legitimate environment blockers before implementation attempts formal compute execution:

- the required task-specific wrapper/config surfaces for execution are still missing when execution is requested:
  - `scripts/slurm/autovla_gr00t_gpu200_multiformat.sh`
  - `configs/training/gr00t_n1d6_gpu200_multiformat.yaml`
  - `configs/dataloader/multiformat_bakeoff.yaml`
- the formal GPU submission path is not defined in a project wrapper/config and execution would have to fall back to raw `srun`/`sbatch`
- the chosen Slurm config/profile still contains `TO_FILL`, points at the wrong partition/cluster, or fails the wrapper’s active-cluster checks
- `srun` or `sbatch` is unavailable on the approved execution host
- the governed evidence/output directories under `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/` cannot be created or used
- the local project environment required to start the bounded benchmark/telemetry commands is missing or broken on the compute path

The following are not `BLOCKED_COMPUTE_ENV` and should be classified differently:

- missing explicit compute authorization fields for the later execution loop:
  `BLOCKED_COMPUTE_AUTH`
- scheduler rejection, partition/QoS/account policy conflict, or any attempt to bypass wrapper policy:
  `BLOCKED_COMPUTE_POLICY`
- a proposal that requires broader scheduler mutation, raw-command bypass, multi-GPU scaling, or out-of-scope execution:
  `BLOCKED_SCOPE`

## Recommendation

Proceed with implementation planning under these compute constraints:

- keep login-node work static only
- keep the store benchmark on compute but CPU-only
- keep telemetry bounded to 1 GPU and 200 steps
- use at most one short `srun` preflight allocation
- collect final evidence through formal wrapper-driven jobs, split by CPU benchmark and per-candidate GPU telemetry
- fail closed on missing GPU-capable wrapper/config instead of improvising raw scheduler commands

## Subagent Retirement Ledger

- child subagents used: none
- retired: yes

## Conclusion

APPROVE
