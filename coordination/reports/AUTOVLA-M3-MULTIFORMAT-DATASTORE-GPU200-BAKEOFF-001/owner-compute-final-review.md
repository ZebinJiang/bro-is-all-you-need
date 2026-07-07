# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 · Owner Compute Final Review

Role: `80-OWNER · Compute/HPC`

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `3573930421a2f9be66b222d602db680a77aadf3f`

Runtime override honored for this dispatch:

- model: `gpt-5.5`
- thinking: `high`

## Evidence Reviewed

- Manager summary:
  - `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/manager-summary.md`
- Wave 9 Compute/HPC report:
  - `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave9.md`
- Wave 11 Compute/HPC report:
  - `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave11.md`
- Wave 12 Data report:
  - `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave12.md`
- Final docs/readme surfaces:
  - `README.md`
  - `docs/benchmarks/README.md`
  - `docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md`
- Wave 11 wrapper evidence:
  - `runs/slurm_debug/autovla-m3-multiformat-gpu200-wave11-raw/logs/srun_command.txt`
  - `runs/slurm_debug/autovla-m3-multiformat-gpu200-wave11-zjh-lerobot-v3-local/logs/srun_command.txt`
- Wave 11 bridge results:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave11-telemetry/raw/outputs/bridge_runtime_result.json`
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave11-telemetry/zjh_lerobot_v3_local/outputs/bridge_runtime_result.json`
- Wave 11 stdout logs:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave11-telemetry/raw/logs/autovla-m3-multiformat-gpu200-wave11-raw.stdout.log`
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave11-telemetry/zjh_lerobot_v3_local/logs/autovla-m3-multiformat-gpu200-wave11-zjh-lerobot-v3-local.stdout.log`

No DevSpace MCP was used. No new compute, tests, Slurm jobs, source edits, config edits, dataset edits, dependency edits, runtime edits, staging, commit, push, or PR mutation were performed by this review.

## Findings

### P1 · Final benchmark doc claims structured telemetry files that are not present in Wave 11 evidence

Status: `REQUEST_CHANGES`

Evidence:

- `docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md` has a `Structured Outputs` section that says the telemetry bridge writes:
  - `telemetry_step_samples.json`
  - `telemetry_aggregate.json`
  - `telemetry_step_table.md`
  - `telemetry_aggregate_table.md`
  - `telemetry_missing_table.md`
  - `telemetry_environment_table.md`
  - `telemetry_summary.md`
  - `telemetry_bridge_plan.json`
  - `base_model_manifest.json`
- Current Wave 11 output roots inspected by this review contain:
  - `bridge_runtime_result.json`
  - stdout/stderr logs
  - `experiment_cfg/**`
  - `processor/**`
  - model/config/training artifacts
  - `checkpoint-200/**`
- Repository search found `base_model_manifest.json` and `telemetry_bridge_plan.json` only under static preflight evidence, not under the Wave 11 telemetry output roots.
- No Wave 11 files named `telemetry_step_samples.json`, `telemetry_aggregate.json`, `telemetry_step_table.md`, `telemetry_aggregate_table.md`, `telemetry_missing_table.md`, `telemetry_environment_table.md`, or `telemetry_summary.md` were found under:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave11-telemetry/raw/outputs`
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave11-telemetry/zjh_lerobot_v3_local/outputs`

Why this matters:

The final benchmark page is linked from `README.md` and `docs/benchmarks/README.md`. Publishing it with nonexistent Wave 11 structured-output file claims would overstate the telemetry artifact surface, even though the core 200-step compute evidence is valid.

Fix direction:

Update `docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md` so the structured-output section matches actual Wave 11 evidence, or clearly label those files as earlier/static-preflight or future structured outputs rather than Wave 11 telemetry outputs. No new compute is required for this fix.

### P2 · Linked benchmark page is currently ignored

Status: publication-surface caution

Evidence:

- `README.md` links to `docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md`.
- `docs/benchmarks/README.md` links to the same file.
- `git check-ignore -v docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md` reports:
  - `.gitignore:235:*/**/*.md`
- `git status --short --ignored docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md` reports:
  - `!! docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md`

Why this matters:

If this linked benchmark page is intended to publish with the PR, it must be explicitly included by the publication owner or the tracked README links should be adjusted. This is not a Compute/HPC evidence blocker, but it is visible in the final docs surface.

Fix direction:

Quality/Data should decide whether to force-add the benchmark page after correcting the structured-output claim, or avoid linking to an ignored page in tracked docs.

## Compute Evidence Review

Wave 11 supports `PASS` for both required telemetry candidates.

Raw baseline:

- candidate: `zjh_lerobot_v21_raw`
- config:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave11-telemetry/configs/zjh_lerobot_v21_raw.yaml`
- `dataloader_num_workers`: `0`
- wrapper evidence:
  - `runs/slurm_debug/autovla-m3-multiformat-gpu200-wave11-raw/logs/srun_command.txt`
- bridge result:
  - `returncode: 0`
- stdout evidence:
  - `train_runtime: 88.1449`
  - `train_steps_per_second: 2.269`
  - `train_loss: 1.128048825263977`
  - `Training completed!`
- disposition:
  - `PASS_200_STEP_TELEMETRY`

Best non-raw:

- candidate: `zjh_lerobot_v3_local`
- config:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave11-telemetry/configs/zjh_lerobot_v3_local.yaml`
- `dataloader_num_workers`: `0`
- wrapper evidence:
  - `runs/slurm_debug/autovla-m3-multiformat-gpu200-wave11-zjh-lerobot-v3-local/logs/srun_command.txt`
- bridge result:
  - `returncode: 0`
- stdout evidence:
  - `train_runtime: 88.8496`
  - `train_steps_per_second: 2.251`
  - `train_loss: 1.1281476402282715`
  - `Training completed!`
- disposition:
  - `PASS_200_STEP_TELEMETRY`

The Wave 9 blocker does not remain as the active compute state. Final tracked README surfaces state Wave 11 return-code-zero telemetry for raw and local-v3 and do not claim the stale Wave 9 `AF_UNIX path too long` blocker as current. The stale Wave 9 discussion remains only in historical manager/report context.

## Scheduler And Job-ID Review

- The Wave 11 runs used the approved wrapper:
  - `scripts/slurm/request_compute_debug.sh`
- The recorded wrapper envelope was:
  - profile: `h800-gpu`
  - partition: `a100`
  - cpus: `16`
  - mem: `64G`
  - gres: `gpu:1`
  - time: `01:00:00`
- Wave 11 report correctly records:
  - `unknown_debug_wrapper_no_job_id`
- Final README / benchmark docs do not claim unsupported Slurm job IDs.
- No scheduler-policy bypass, raw `sbatch`, scheduler mutation, queue mutation, or broader retry is visible in the reviewed final surfaces.

## Publication Compute Decision

No additional compute is required before publication to satisfy the Compute/HPC evidence requirement. The remaining requested change is documentation-only and should align the final benchmark page with the actual Wave 11 output files.

## DevSpace MCP Compliance

- DevSpace MCP used: no

## Subagent Retirement Ledger

- child subagents used: none
- write-capable child subagents used: none
- retired: yes

## Conclusion

`REQUEST_CHANGES`

Reason:

The Wave 11 compute evidence itself supports `PASS` for both required 200-step telemetry candidates, and no new compute is needed. However, the final linked benchmark documentation currently overclaims structured telemetry output files that are not present in the Wave 11 evidence roots. Correct that documentation surface before publication, and keep the Wave 11 compute evidence unchanged.
