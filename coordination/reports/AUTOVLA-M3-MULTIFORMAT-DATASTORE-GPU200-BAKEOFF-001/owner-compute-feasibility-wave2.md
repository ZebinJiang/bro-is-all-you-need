# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 · Compute/HPC Feasibility Wave 2

Role: `80-OWNER · Compute/HPC`

## 1. Workspace verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `3573930421a2f9be66b222d602db680a77aadf3f`
- `git status --short --branch`:
  - `## dev/feat-autovla-multiformat-datastore-gpu200-bakeoff...origin/main`
  - ` M README.md`
  - ` M coordination/PROGRAM_STATE.yaml`
  - ` M coordination/TASK_INDEX.yaml`
  - ` M docs/benchmarks/README.md`
  - `?? autovla/dataloader/stores/`
  - `?? autovla/training/telemetry/`
  - `?? configs/dataloader/`
  - `?? configs/training/`
  - `?? coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/`
  - `?? coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
  - `?? scripts/slurm/autovla_gr00t_gpu200_multiformat.sh`
  - `?? tests/dataloader/test_multiformat_datastore_bakeoff.py`
  - `?? tests/training/test_gpu200_multiformat_telemetry.py`

## 2. Current blocker map

1. Data wave 1 is scaffold-level only. It established candidate surfaces for `zjh_lerobot_v21_raw`, `zjh_lerobot_v3_local`, `zjh_webdataset_tar`, and `zjh_robodm_container_v1`, but the later data packet still says `configs/dataloader/multiformat_bakeoff.yaml` is missing and data wave 2 is required to make the datastore side compute-runnable.
2. Training wave 1 is still metadata-only. `autovla/training/telemetry/__main__.py` advertises `run-governed` as bounded metadata-only telemetry emission, and the delivered report already states the current surface is compute-ready surface rather than compute evidence.
3. The current training config is not yet honest for a real GPU200 submission. `configs/training/gr00t_n1d6_gpu200_multiformat.yaml` fixes `max_steps: 200` and the correct profile, but it also declares `gres: none`, which blocks this config from being treated as a real GPU telemetry launch surface.
4. AutoVLA's local model side remains fail-closed. `autovla/models/gr00t_n1d6/adapter.py` still declares `support_status="unavailable_missing_assets"` and the reviewed model plan keeps the GR00T adapter metadata-only.
5. `zjh_lerobot_v3_local` is still an explicit blocked candidate in the current data execution evidence, with status `NOT_RUN_DEPENDENCY_BLOCKED`.
6. A real external GR00T runtime target does exist under the authorized read-only exception. `/home/cz-jzb/workspace/Isaac-GR00T17/base_model/GR00T-N1.6-3B` is present, and the Isaac GR00T docs/configs show a real fine-tune path that expects `base_model_path`, `dataset_path`, `modality_config_path`, and `--num-gpus`.

## 3. Recommended exact job topology

1. One CPU-only datastore benchmark job for bounded store-build and load-benchmark evidence across the approved candidate set. This stays separate from any GPU job because it answers the store-layout question and does not need model runtime.
2. One 1-GPU, 200-step telemetry job per candidate that has both:
   - a compute-runnable datastore artifact or raw dataset path; and
   - an honest bridge into a real GR00T training surface.
3. Optional 2-GPU communication benchmarking should remain a later, separate job family. It is not needed for the first execution packet. It becomes useful only after the 1-GPU path is proven and only if the eventual bridge design actually introduces distributed communication worth measuring.

## 4. Which candidates are likely runnable for real GPU200 and why

- `zjh_lerobot_v21_raw`: most likely first real GPU200 candidate. The authorized external Isaac GR00T docs explicitly describe a LeRobot-v2-flavor dataset with `meta/modality.json`, and this raw path is closest to that runtime expectation.
- `zjh_webdataset_tar`: not yet honestly runnable for the real GPU200 step from the current repo alone. It is a credible store candidate, but the current AutoVLA repo does not yet show a real GR00T training bridge from this artifact into Isaac GR00T fine-tuning.
- `zjh_robodm_container_v1`: same conclusion as `zjh_webdataset_tar`. It is credible for store-side comparison, but the present repo does not yet provide an execution bridge that makes it a real 200-step GR00T candidate.
- `zjh_lerobot_v3_local`: not runnable at this time. The current data execution evidence keeps it in `NOT_RUN_DEPENDENCY_BLOCKED`, and there is no new wave-2 execution evidence yet proving that this changed.

## 5. Which candidates are likely load-benchmark-only and why

- `zjh_webdataset_tar`: likely load-benchmark-only until a later training bridge or conversion path can present it to the GR00T runtime in an accepted dataset shape.
- `zjh_robodm_container_v1`: likely load-benchmark-only for the same reason. Store-side timing is meaningful now; real 200-step participation is not yet justified.
- `zjh_lerobot_v3_local`: currently blocked rather than runnable. If the later data wave cannot produce an honest offline local route, it remains a comparison row rather than a real GPU200 participant.

## 6. Whether AutoVLA needs a new Training bridge wave before compute can start

Yes.

The most realistic bounded training execution path is not the current AutoVLA-local telemetry package by itself. The current telemetry code is metadata-only, the local model adapter remains fail-closed, and the current config still sets `gres: none`.

The honest path is a governed AutoVLA-generated wrapper that launches a read-only `Isaac-GR00T17` fine-tune surface while preserving AutoVLA-owned manifests, tables, output roots, and guardrails. Without that bridge wave, the repo does not yet have a truthful path from the reviewed datastore candidates into a real 1-GPU, 200-step GR00T run.

For candidates that cannot honestly join the 200-step run because this bridge does not yet exist, the recommended exact compute-side status token is:

- `NOT_RUN_TRAINING_BRIDGE_BLOCKED`

For `zjh_lerobot_v3_local`, the existing explicit token remains correct until proven otherwise:

- `NOT_RUN_DEPENDENCY_BLOCKED`

## 7. Preflight checklist

1. Verify dataset path visibility for the chosen candidate on the compute route.
2. Verify candidate artifact visibility for store-built candidates and confirm the emitted manifest path is stable.
3. Verify local checkpoint/base-model visibility for `/home/cz-jzb/workspace/Isaac-GR00T17/base_model/GR00T-N1.6-3B`.
4. Verify env/tool visibility for the exact runtime wrapper, Python or `uv` entrypoint, and any required local package roots.
5. Verify wrapper/config presence for:
   - `scripts/slurm/autovla_gr00t_gpu200_multiformat.sh`
   - the eventual datastore bakeoff config
   - the eventual training bridge config or bridge wrapper
6. Verify offline-local environment settings before first submission:
   - `WANDB_MODE=offline`
   - `HF_HUB_OFFLINE=1`
   - `TRANSFORMERS_OFFLINE=1`
   - `HF_DATASETS_OFFLINE=1`
7. Verify the first real GPU job config requests actual GPU resources rather than `gres: none`.
8. Verify governed output roots under project-local `runs/` or task-owned governed output paths before submission.
9. Verify the execution packet records that the first GPU run is a bounded 200-step telemetry/training probe, not a training-readiness or model-compatibility acceptance claim.

## 8. DevSpace MCP compliance

DevSpace MCP was not used. This review was completed with local read-only inspection plus the allowed owner report write.

## 9. Subagent retirement ledger

- Subagents used: none
- Retired: yes

## 10. Conclusion

`BLOCKED_COMPUTE_ENV`

Reason: the later execution packet is not yet ready for honest compute submission because the current AutoVLA training surface is metadata-only, the current GPU config still declares `gres: none`, the datastore wave still lacks the promised compute-runnable bakeoff config/evidence, and a real AutoVLA-to-Isaac GR00T training bridge has not yet been implemented.
