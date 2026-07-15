# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 · Owner Compute Execute Wave 3

Role: `70-OWNER · Compute/HPC`

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `3573930421a2f9be66b222d602db680a77aadf3f`

## Start-Gate Verification

All required upstream owner gates were present and matched the packet:

1. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave2.md`
   - conclusion: `PASS`
2. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-model-feasibility-wave2.md`
   - conclusion: `APPROVE_BOUNDARY`
3. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-execute-wave3.md`
   - conclusion: `PASS`

## Actual Wrapper Route Used

All scheduler-facing actions used the approved project wrapper only:

- `scripts/slurm/request_compute_debug.sh`

No raw `srun` or `sbatch` was invoked outside the project wrapper.

## Phase A — Static Bridge And Path Verification

Static bridge verification passed under the allowed task-owned compute evidence root:

- concrete bridge config:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/static-preflight/bridge_preflight_raw.yaml`
- bridge-owned manifests and rendered wrapper:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/static-preflight/manifests/base_model_manifest.json`
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/static-preflight/manifests/checkpoint_manifest.json`
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/static-preflight/rendered-wrapper/autovla_gr00t_gpu200_multiformat.sbatch`
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/static-preflight/rendered-wrapper/telemetry_bridge_plan.json`

What was verified:

- actual bridge entrypoint exists:
  - `autovla.training.telemetry bridge-run`
- actual datastore benchmark entrypoint exists:
  - `python -m autovla.dataloader.stores run --config configs/dataloader/multiformat_bakeoff.yaml`
- local model root exists:
  - `/home/cz-jzb/workspace/Isaac-GR00T17/base_model/GR00T-N1.6-3B`
- local Isaac entrypoint exists:
  - `/home/cz-jzb/workspace/Isaac-GR00T17/gr00t/experiment/launch_finetune_n1d6.py`
- local Isaac modality config exists:
  - `/home/cz-jzb/workspace/Isaac-GR00T17/gr00t/configs/data/black_rubber.py`
- sanctioned local Isaac env exists and was used as runtime evidence:
  - `/home/cz-jzb/workspace/Isaac-GR00T17/.venv/bin/python`
- offline guards are present in the bridge config and rendered wrapper:
  - `WANDB_MODE=offline`
  - `HF_HUB_OFFLINE=1`
  - `TRANSFORMERS_OFFLINE=1`
  - `HF_DATASETS_OFFLINE=1`

Important bridge-runtime finding:

- the bridge is compute-executable only when the runtime environment includes:
  - `python_executable=/home/cz-jzb/workspace/Isaac-GR00T17/.venv/bin/python`
  - `PYTHONPATH=/home/cz-jzb/workspace/Isaac-GR00T17`
- AutoVLA's current toolenv alone is not enough for the Isaac entrypoint because it lacks Isaac's `tyro` dependency.

## Phase B — Dry-Run Preflight Result

- result: `PASS`
- run id: `autovla-m3-multiformat-preflight-dryrun`
- evidence note:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/preflight-dryrun.md`
- wrapper evidence:
  - `runs/slurm_debug/autovla-m3-multiformat-preflight-dryrun/logs/srun_command.txt`

Resolved dry-run envelope:

- partition: `a100`
- cpus: `16`
- mem: `64G`
- gres: `gpu:1`
- time: `01:00:00`

## Phase C — Real Preflight Result

- result: `PASS`
- run id: `autovla-m3-multiformat-preflight-real`
- evidence note:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/preflight-real.md`
- wrapper evidence:
  - `runs/slurm_debug/autovla-m3-multiformat-preflight-real/logs/srun_command.txt`

Observed real compute evidence:

- shell-sandbox wrapper attempt failed with `Operation not permitted`
- exact same approved wrapper command succeeded after command-local escalation
- compute node observed:
  - `instance-yp83uwa1-1`
- GPU observed:
  - `NVIDIA A100-SXM4-80GB`
- bridge/config help-path evidence on compute:
  - readonly dataset root visible
  - readonly Isaac root visible
  - readonly base-model root visible
  - AutoVLA toolenv python visible
  - Isaac local `.venv` python visible
  - `nvidia-smi -L` succeeded
  - `python -m autovla.training.telemetry validate-config` succeeded
  - Isaac `launch_finetune_n1d6.py --help` succeeded with explicit `PYTHONPATH`

## Phase D — Real Benchmark Execution Result

- result: `ATTEMPTED_AND_BLOCKED`
- run id: `autovla-m3-multiformat-store-benchmark`
- wrapper evidence:
  - `runs/slurm_debug/autovla-m3-multiformat-store-benchmark/logs/srun_command.txt`
- requested envelope:
  - partition: `a100`
  - cpus: `32`
  - mem: `128G`
  - gres: `none`
  - time: `06:00:00`
- exact scheduler rejection:
  - `srun: error: QOSMaxWallDurationPerJobLimit`
  - `srun: error: Unable to allocate resources: Job violates accounting/QOS policy (job submit limit, user's size and/or time limits)`

Compute governance consequence:

- this is a scheduler policy hard stop, not a code-path crash
- after this rejection, I did not invent a shorter benchmark walltime or alternate resource shape
- I did not bypass the project wrapper

Benchmark output root was therefore not produced:

- expected root:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/`
- actual status:
  - not produced because the scheduler rejected the benchmark allocation before launch

## Runnable Candidate Set

No runnable candidate set was derived from actual benchmark outputs in this wave.

Reason:

- the real store benchmark allocation was rejected by scheduler policy before execution
- without actual benchmark outputs, no packet-faithful ranking or fallback selection across all four candidates can be claimed

## Phase E — 1-GPU Telemetry Execution Result By Candidate

No candidate telemetry jobs were launched in this wave.

Per-candidate status:

- `zjh_lerobot_v21_raw`: `NOT_RUN_UPSTREAM_BENCHMARK_POLICY_BLOCKED`
- `zjh_lerobot_v3_local`: `NOT_RUN_UPSTREAM_BENCHMARK_POLICY_BLOCKED`
- `zjh_webdataset_tar`: `NOT_RUN_UPSTREAM_BENCHMARK_POLICY_BLOCKED`
- `zjh_robodm_container_v1`: `NOT_RUN_UPSTREAM_BENCHMARK_POLICY_BLOCKED`

Why telemetry was not attempted:

1. the compute benchmark stage is the packet-authorized source for the runnable candidate set;
2. that stage was rejected by scheduler policy before launch;
3. compute governance requires a hard stop on policy rejection rather than inventing a new benchmark envelope.

## Whether Training / Model Bridge Was Sufficient

Yes for preflight, not yet proven for real bounded telemetry.

What is now evidenced:

- the bridge surface is honest and launch-shaped
- static config validation works
- local base-model manifest writing works
- rendered wrapper writing works
- the Isaac entrypoint is callable on a real compute node when the runtime uses:
  - Isaac local `.venv`
  - `PYTHONPATH=/home/cz-jzb/workspace/Isaac-GR00T17`

What is not yet evidenced:

- a completed 200-step candidate telemetry run
- real candidate output tables under `gpu200/<candidate>/`
- checkpoint correctness
- model compatibility validation
- training readiness

## Remaining Blocker For Publication-Quality Summary Tables

Yes, a blocker remains.

The blocker is not source correctness in the bridge or wrapper surfaces. The blocker is that the packet's preferred real benchmark envelope (`a100`, `32 CPU`, `128G`, `06:00:00`, `gres=none`) was rejected by current scheduler policy with `QOSMaxWallDurationPerJobLimit`, and no narrower benchmark alternative was authorized in this wave after that hard stop.

## Optional 2-GPU Communication

- skipped: yes
- reason: packet does not require it before 1-GPU success, and the benchmark stage blocked earlier on scheduler policy

## Exact Evidence Paths

Task-owned compute evidence:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/static-preflight/bridge_preflight_raw.yaml`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/static-preflight/manifests/base_model_manifest.json`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/static-preflight/manifests/checkpoint_manifest.json`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/static-preflight/rendered-wrapper/autovla_gr00t_gpu200_multiformat.sbatch`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/static-preflight/rendered-wrapper/telemetry_bridge_plan.json`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/preflight-dryrun.md`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/preflight-real.md`

Wrapper-owned Slurm debug evidence:

- `runs/slurm_debug/autovla-m3-multiformat-preflight-dryrun/logs/srun_command.txt`
- `runs/slurm_debug/autovla-m3-multiformat-preflight-real/logs/srun_command.txt`
- `runs/slurm_debug/autovla-m3-multiformat-store-benchmark/logs/srun_command.txt`

No `runs/slurm/autovla-m3-multiformat-store-benchmark/**` output was produced in this wave because the benchmark launch was rejected before execution.

## DevSpace MCP Compliance

- DevSpace MCP used: no

## Subagent Retirement Ledger

- child subagents used: none
- write-capable child subagents used: none
- no parallel write: yes
- retired: yes

## Conclusion

`BLOCKED_SCOPE`

Reason: compute preflight and bridge verification succeeded, but the real benchmark stage hit a scheduler policy hard stop (`QOSMaxWallDurationPerJobLimit`) on the packet's preferred `06:00:00` CPU benchmark envelope, and this wave did not authorize a narrower replacement envelope after that hard stop. Without a benchmark launch, no packet-faithful runnable candidate set or fallback telemetry set could be claimed.
