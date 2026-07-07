# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 · Owner Model Feasibility Wave 2

## 1. Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `3573930421a2f9be66b222d602db680a77aadf3f`
- `git status --short --branch`:
  - branch: `## dev/feat-autovla-multiformat-datastore-gpu200-bakeoff...origin/main`
  - current worktree contains the expected task-local WIP under `autovla/training/telemetry/**`, `configs/training/**`, `scripts/slurm/**`, `docs/benchmarks/**`, `README.md`, task reports, and focused tests.
- note: shell emitted `whoami: cannot find name for user ID 2000`; repository evidence remained usable.

## 2. Current Model-Runtime Blocker Map

### Already acceptable today

- `autovla/models/gr00t_n1d6/adapter.py` remains fail-closed:
  - `support_status="unavailable_missing_assets"`
  - no runtime asset paths filled by default
  - no `forward` or `predict_action` support
- `autovla/models/family.py` still enforces metadata-only family invariants:
  - `no_weight_load=True`
  - `no_tokenizer_load=True`
  - `no_network=True`
  - `no_checkpoint_download=True`
- `autovla/training/telemetry/**` is still a telemetry surface, not a training runtime:
  - `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_DATASETS_OFFLINE=1` in rendered Slurm script
  - telemetry output labels `model_runtime_status="metadata_only_unverified"`
  - no model load path exists in the reviewed telemetry files

### Not yet sufficient for a real bounded compute launch

- `configs/training/gr00t_n1d6_gpu200_multiformat.yaml` currently carries only a single string field:
  - `checkpoint_manifest_path: ${AUTOVLA_GR00T_N1D6_CHECKPOINT_MANIFEST}`
- AutoVLA does not yet define, in this task surface, a GR00T runtime-asset manifest schema that binds:
  - the exact local model root
  - the exact local processor/config/index files
  - the exact read-only/offline rules
  - the exact allowed claim boundary for the resulting 200-step run

This is the key remaining Model-side gap. It is a governance gap, not proof that the local GR00T candidate is unusable.

## 3. Allowed Local-Checkpoint Boundary

Model considers the later compute wave allowed to use the local path
`/home/cz-jzb/workspace/Isaac-GR00T17/base_model/GR00T-N1.6-3B`
only under all of the following conditions:

1. The path is treated as a local read-only base-model asset root, not as proof of compatibility by itself.
2. No download, cache fill, remote resolution, or HF online fallback is allowed.
3. The later bridge may read only the explicit files listed in a governed manifest.
4. The later bridge must not mutate the Isaac-GR00T17 repo or the base-model directory.
5. The later run must be described as bounded runnable telemetry only, never as checkpoint correctness or training readiness.

Static evidence supports that this local path is a real offline asset tree:

- external repo root: `/home/cz-jzb/workspace/Isaac-GR00T17`
- external repo HEAD: `c038416a6c9eae0de6ff72313f4ccfb04ab4fe35`
- local base-model files observed:
  - `README.md`
  - `LICENSE`
  - `config.json`
  - `processor_config.json`
  - `model.safetensors.index.json`
  - `model-00001-of-00002.safetensors`
  - `model-00002-of-00002.safetensors`
  - `embodiment_id.json`
  - `statistics.json`
  - model card companion docs: `EXPLAINABILITY.md`, `PRIVACY.md`, `SAFETY_and_SECURITY.md`

The Isaac-side docs also support the offline-local interpretation:

- `sbatch/README.md` says N1.6 scripts use `base_model/GR00T-N1.6-3B`
- missing local model directories fail before training rather than falling back to remote Hugging Face repos
- `HF_HUB_OFFLINE` defaults to `1` unless the caller overrides it

## 4. Required Checkpoint / Manifest Fields

Model does require a new explicit AutoVLA-governed manifest artifact before Training/Compute launch a real bounded 200-step run.

The existing `checkpoint_manifest_path` placeholder is not enough on its own. A later compute wave needs one governed JSON/YAML artifact that pins the exact local model asset boundary.

### Mandatory fields

- `schema_version`
- `model_family_key`: `gr00t-n1d6`
- `model_registry_key`: `gr00t-n1d6`
- `support_status_at_launch`: must remain a bounded-launch status, not a blanket compatibility claim
- `source_repo_root`: `/home/cz-jzb/workspace/Isaac-GR00T17`
- `source_repo_head`: exact local commit used for the run
- `base_model_root`: `/home/cz-jzb/workspace/Isaac-GR00T17/base_model/GR00T-N1.6-3B`
- `path_policy` object:
  - `read_only: true`
  - `local_only: true`
  - `no_download: true`
  - `no_cache_probe: true`
  - `no_mutation: true`
  - `hf_online: false`
- `required_files` object with explicit paths for:
  - `README.md`
  - `LICENSE`
  - `config.json`
  - `processor_config.json`
  - `model.safetensors.index.json`
  - `model-00001-of-00002.safetensors`
  - `model-00002-of-00002.safetensors`
  - `embodiment_id.json`
  - `statistics.json`
- `required_file_presence`: boolean map proving those files were observed before launch
- `weight_inventory` object:
  - shard filenames
  - shard sizes in bytes
  - index `metadata.total_size`
- `license_and_card` object:
  - local `LICENSE` path
  - local `README.md` path
  - local subcard paths if used in evidence
  - explicit note that the README/license are local evidence, not AutoVLA compatibility approval
- `runtime_offline_env` object:
  - `HF_HUB_OFFLINE=1`
  - `TRANSFORMERS_OFFLINE=1`
  - `HF_DATASETS_OFFLINE=1`
  - `WANDB_MODE=offline` if present
- `claim_boundary` object:
  - `runnable_bounded_telemetry_only: true`
  - `checkpoint_correctness_validated: false`
  - `training_readiness_validated: false`
  - `model_compatibility_validated: false`
  - `tokenizer_processor_validated: false`

### Strongly recommended fields

- `config_json_size_bytes`
- `processor_config_size_bytes`
- `safetensors_index_size_bytes`
- `statistics_json_size_bytes`
- `manifest_author`
- `manifest_timestamp`
- `task_id`
- `dataset_fingerprint`
- `transform_fingerprint`
- `statistics_fingerprint`
- `datastore_name`
- `max_steps`: must be `200`

### Why Model requires this manifest

Without this artifact, the later bridge would still be relying on an underspecified string path. That is too loose for a real bounded compute launch involving a local GR00T checkpoint tree.

## 5. What a Later Successful 200-Step Run May And May Not Claim

### Allowed claims

- the selected datastore candidate was runnable through the governed 200-step telemetry path
- the local offline GR00T base-model asset path was sufficient to let the bounded run start under the approved bridge
- the run produced bounded timing/utilization/loader telemetry useful for datastore comparison
- the result is suitable as decision-support evidence for loader/backend comparison

### Forbidden claims

- model compatibility validated
- checkpoint correctness validated
- tokenizer or processor correctness validated
- training readiness validated
- fine-tune readiness validated
- action-quality correctness validated
- deployment or inference readiness validated
- general GR00T support in AutoVLA validated

In short: success may support `runnable bounded telemetry only`, and at most `loader/backend comparison evidence only`.

## 6. AutoVLA-Governed Bridge To Read-Only Isaac-GR00T17

Model considers a bridge acceptable, but only in the narrow form below:

- AutoVLA remains the governing wrapper and report surface.
- Isaac-GR00T17 may be used as a read-only runtime entrypoint source.
- The bridge must pass explicit local paths and offline environment flags.
- The bridge must not add path discovery, fallback download, or compatibility overclaim behavior.
- The bridge must not hand authorship of the safety boundary to Isaac docs implicitly; AutoVLA must restate the allowed claims and offline restrictions in its own manifest/reporting.

Model does **not** require fully AutoVLA-native runtime ownership before this bounded telemetry wave. For this tranche, wrapper-owned governance around a read-only Isaac runtime is enough, provided the manifest above exists and the claim boundary stays narrow.

## 7. Trigger Conditions

### `READY_FOR_USER_DECISION_MODEL_CHECKPOINT`

Trigger this if any of the following become true:

- the compute wave cannot produce the explicit manifest described above
- the chosen local model root changes from the reviewed path
- license/model-card provenance becomes ambiguous
- the run needs additional local assets not captured in the governed manifest
- the bridge needs to load or validate more than the approved local read-only files in order to make a stronger compatibility claim

### `BLOCKED_SCOPE`

Trigger this if the proposed bridge or run would:

- download from Hugging Face or any network source
- probe caches or alternate directories implicitly
- mutate Isaac-GR00T17 or the base-model path
- broaden into full training/fine-tune semantics beyond the fixed 200-step telemetry envelope
- require new dependency installation or uncontrolled runtime expansion outside the task authorization

### `REQUEST_CHANGES`

Trigger this if the compute/training surface remains bounded but is still missing one of:

- the explicit manifest artifact
- offline environment enforcement
- clear claim-boundary wording in outputs
- exact local path pinning and file inventory
- a wrapper contract that keeps AutoVLA, not Isaac, as the governance owner

## 8. DevSpace MCP Compliance

- DevSpace MCP used: no

## 9. Subagent Retirement Ledger

- child subagents used: none
- retired: yes

## Conclusion

APPROVE_BOUNDARY
