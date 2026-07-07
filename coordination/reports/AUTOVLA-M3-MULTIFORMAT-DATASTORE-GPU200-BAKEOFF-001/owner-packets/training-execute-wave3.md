# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 Training Execute Wave 3 Packet

## Role

You are `20-OWNER · Training`.

This wave starts only after:

- Data wave 2 report exists and concludes `PASS`
- Model feasibility wave 2 exists and concludes `APPROVE_BOUNDARY`
- Training bridge plan wave 2 exists and concludes `APPROVE_BRIDGE_PLAN`
- Compute/HPC feasibility wave 2 exists and concludes `BLOCKED_COMPUTE_ENV`
  specifically because the bridge and honest GPU config were still missing

Use:

- model: `gpt-5.4`
- thinking: `high`

Do not use DevSpace MCP.
Do not create child write-capable subagents.
No parallel source writes.

## Workspace

- worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- expected HEAD for this write wave: `3573930421a2f9be66b222d602db680a77aadf3f`

Before writing, verify:

- `pwd`
- `git rev-parse --show-toplevel`
- `git branch --show-current`
- `git rev-parse HEAD`

## Allowed write scope

- `autovla/training/telemetry/**`
- `configs/training/gr00t_n1d6_gpu200_multiformat.yaml`
- `scripts/slurm/autovla_gr00t_gpu200_multiformat.sh`
- `tests/training/**`
- `docs/benchmarks/**`
- `README.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-execute-wave3.md`

Do not write:

- `autovla/dataloader/stores/**`
- `requirements/**`
- `pyproject.toml`
- `Makefile`
- `datasets/readonly/**`
- `datasets/working/**`
- `/home/cz-jzb/workspace/Isaac-GR00T17/**`

Read-only external exception allowed:

- `/home/cz-jzb/workspace/Isaac-GR00T17/**`

## Manager handoff facts you must treat as true

### From Data wave 2

Report:

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave2.md`

Conclusion:

- `PASS`

Important Data outputs now available:

- shared fairness manifest target:
  - `datasets/working/autovla_multiformat_bakeoff_gpu200/multiformat_bakeoff/multiformat_sample_window_manifest.json`
- runnable datastore CLI:
  - `python -m autovla.dataloader.stores run --config configs/dataloader/multiformat_bakeoff.yaml`
- compute-runnable datastore candidates:
  - `zjh_lerobot_v21_raw`
  - `zjh_lerobot_v3_local`
  - `zjh_webdataset_tar`
  - `zjh_robodm_container_v1`

### From Model wave 2

Report:

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-model-feasibility-wave2.md`

Conclusion:

- `APPROVE_BOUNDARY`

Hard Model requirement for this wave:

- add an explicit AutoVLA-governed local model / checkpoint manifest surface
- keep claim boundary narrow:
  - runnable bounded telemetry only
  - not checkpoint correctness
  - not training readiness
  - not model compatibility validation

Reviewed local model root:

- `/home/cz-jzb/workspace/Isaac-GR00T17/base_model/GR00T-N1.6-3B`

Reviewed runtime entrypoint family:

- `/home/cz-jzb/workspace/Isaac-GR00T17/gr00t/experiment/launch_finetune_n1d6.py`

### From Training bridge plan wave 2

Report:

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-bridge-plan-wave2.md`

Conclusion:

- `APPROVE_BRIDGE_PLAN`

Hard Training design decision:

- keep `autovla.training.telemetry` as the telemetry/reporting substrate
- add a distinct real-run bridge layer instead of pretending
  `run-governed` already launches real GR00T runtime
- prefer subprocess / wrapper handoff to Isaac-GR00T17, not direct long-term
  runtime import ownership by AutoVLA

### From Compute/HPC wave 2

Report:

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-feasibility-wave2.md`

Conclusion:

- `BLOCKED_COMPUTE_ENV`

Reason you are solving in this wave:

- current telemetry package is metadata-only
- current training config still says `gres: none`
- no honest AutoVLA-to-Isaac bounded bridge exists yet

## Exact wave intent

This is a write-capable bridge implementation wave.

The goal is **not** to run compute yet.

The goal is to convert the current metadata-only telemetry surface into a
compute-executable **bridge surface** that later Compute/HPC can use for:

- one real 1-GPU bounded `max_steps = 200` GR00T-N1D6 telemetry run
- later repeated per-candidate runs over the runnable datastore set

You must implement the minimum honest bridge that:

1. keeps AutoVLA as the governance owner;
2. uses Isaac-GR00T17 only as a read-only runtime entrypoint source;
3. pins local model/checkpoint provenance through an explicit manifest;
4. renders exact offline/local argv and Slurm script surfaces;
5. does not submit jobs in this wave;
6. does not overclaim compatibility or training readiness.

## Required implementation outcomes

### 1. Add a distinct bridge surface under `autovla/training/telemetry/**`

Implement a clear bridge layer for the later real run. It may live under names
such as:

- `bridge.py`
- `bridge_config.py`
- `bridge_manifest.py`
- `bridge_runtime.py`

The exact file names are up to you, but the behavior must be explicit.

The old metadata-only path must remain clearly separate from the real-run
bridge surface.

It must stay obvious that:

- `run-governed` is not the real Isaac launch
- the new bridge surface is the later real bounded-run entry

### 2. Add bridge config validation

Extend the training config surface so it can express, at minimum:

- `run_id`
- `model_family_key`
- `model_registry_key`
- `env_profile`
- `datastore_name`
- `candidate_store_root`
- `sample_window_manifest_path`
- `sample_window_manifest_fingerprint`
- `dataset_fingerprint`
- `transform_fingerprint`
- `statistics_fingerprint`
- `isaac_project_root`
- `isaac_entrypoint_path`
- `python_executable`
- `base_model_root`
- `base_model_manifest_path`
- `checkpoint_manifest_path`
- `output_dir`
- `logs_root`
- `table_output_root`
- `max_steps`
- `sampling_interval_steps`
- `slurm_partition`
- `slurm_account`
- `cpus_per_task`
- `memory`
- `time_limit`
- `gres`
- `num_gpus`
- `wandb_mode`
- `hf_hub_offline`
- `transformers_offline`
- `hf_datasets_offline`
- `allow_network`
- `allow_checkpoint_download`
- `require_compute_node`

Validation rules:

- `max_steps` must still be exactly `200`
- `num_gpus` must be exactly `1` in this wave
- `gres` must no longer be `none`
- required fingerprints must be non-empty
- all reviewed local path fields must be non-empty text
- `allow_network` must be `false`
- `allow_checkpoint_download` must be `false`
- `require_compute_node` must be `true`
- `wandb_mode` must be offline/disabled only

### 3. Add explicit local base-model manifest generation / rendering surface

Implement an AutoVLA-owned manifest schema and writer/renderer that pins the
reviewed local base-model boundary.

Do not read model weights semantically. Only inventory / verify file presence
and emit provenance metadata.

Mandatory manifest content must include:

- `schema_version`
- `task_id`
- `model_family_key`
- `model_registry_key`
- `support_status_at_launch`
- `source_repo_root`
- `source_repo_head`
- `base_model_root`
- `path_policy`
  - `read_only`
  - `local_only`
  - `no_download`
  - `no_cache_probe`
  - `no_mutation`
  - `hf_online`
- `required_files`
- `required_file_presence`
- `weight_inventory`
- `license_and_card`
- `runtime_offline_env`
- `claim_boundary`
  - `runnable_bounded_telemetry_only`
  - `checkpoint_correctness_validated`
  - `training_readiness_validated`
  - `model_compatibility_validated`
  - `tokenizer_processor_validated`

The reviewed required files are:

- `README.md`
- `LICENSE`
- `config.json`
- `processor_config.json`
- `model.safetensors.index.json`
- `model-00001-of-00002.safetensors`
- `model-00002-of-00002.safetensors`
- `embodiment_id.json`
- `statistics.json`

This manifest must be AutoVLA-owned output. Do not commit an instantiated local
manifest with absolute user paths into source control.

### 4. Render an honest real-run command / plan surface

Implement a bridge command builder / plan emitter that produces the later real
bounded launch command to Isaac-GR00T17.

The rendered command must target:

- `gr00t/experiment/launch_finetune_n1d6.py`

through the configured local Python executable.

The rendered argv must include, at minimum:

- `--base-model-path`
- `--dataset-path`
- `--embodiment-tag`
- `--modality-config-path` when required
- `--num-gpus 1`
- `--output-dir`
- `--max-steps 200`
- batch / worker fields when your config carries them

This wave may render the command and wrapper.
This wave must not execute the real compute launch.

### 5. Upgrade the Slurm wrapper from metadata-only to bridge-ready

Update:

- `scripts/slurm/autovla_gr00t_gpu200_multiformat.sh`
- any related `autovla/training/telemetry/slurm.py`

The wrapper should now render a later executable bridge script / plan that:

- uses the bridge entry rather than metadata-only `run-governed`
- exports offline env guards
- records governed outputs/logs/manifest paths
- uses real 1-GPU resource intent, not `gres: none`
- still does not submit the job in this wave

### 6. Focused tests

Add/update focused tests that prove:

- config validation accepts the new bridge contract
- `num_gpus=1` / `max_steps=200` / offline flags are enforced
- `gres=none` is rejected
- bridge command rendering is deterministic
- base-model manifest rendering is deterministic for a tiny local fixture
  or controlled test double
- rendered wrapper contains:
  - offline env flags
  - local-only model/dataset paths
  - Isaac entrypoint
  - `max_steps 200`
- no test starts real training
- no test reads remote network resources

Use local tiny fixtures / tmp paths only.

### 7. Docs and README

Update docs/README only as needed to keep the contract honest.

Allowed changes:

- clarify that the bridge surface now exists
- clarify that real compute evidence is still pending
- clarify the claim boundary and offline/local-only rules

Do not claim:

- backend winner selected
- training readiness
- model compatibility validated
- compute evidence already exists

## Non-goals for this wave

- no real compute execution
- no Slurm submission
- no GPU run
- no W&B online
- no HF online
- no model download
- no dataloader/store edits
- no dataset conversion work
- no new dependency installation

## Validation commands

Use the root project-local toolenv.

At minimum run:

- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m pytest tests/training/test_gpu200_multiformat_telemetry.py -v`
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m ruff check autovla/training/telemetry tests/training/test_gpu200_multiformat_telemetry.py`
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/pyright --venvpath /home/cz-jzb/workspace/vla-flywheel/runs/tmp -p pyrightconfig.autovla.json autovla/training/telemetry tests/training/test_gpu200_multiformat_telemetry.py`
- `PYTHONPYCACHEPREFIX=/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff/runs/tmp/pycache /home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m py_compile autovla/training/telemetry/*.py tests/training/test_gpu200_multiformat_telemetry.py`
- `git diff --check`

If directory-level Black hangs again in this worktree, use the established
changed-file fallback and record it explicitly.

## Required owner report

Write exactly one report:

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-execute-wave3.md`

The report must include:

- workspace verification
- files changed
- bridge files added/updated
- config fields added/changed
- whether `gres: none` was removed
- exact bridge command / wrapper surfaces now available
- exact base-model manifest surface now available
- validation commands and results
- remaining compute-evidence dependency, if any
- DevSpace MCP compliance
- subagent retirement ledger

## Allowed conclusion values

- `PASS`
- `REQUEST_CHANGES`
- `BLOCKED_TEST`
- `BLOCKED_SCOPE`
- `READY_FOR_USER_DECISION_MODEL_CHECKPOINT`

## Finish condition

This wave is successful only if:

1. the bridge surface is real and distinct from metadata-only `run-governed`;
2. the training config is honest for a later 1-GPU, 200-step run;
3. the local base-model manifest surface exists and stays AutoVLA-owned;
4. focused pytest / Ruff / strict Pyright pass on the changed training surface;
5. the report is written at the required path.
