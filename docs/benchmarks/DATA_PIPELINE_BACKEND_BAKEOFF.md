# AutoVLA ZJH Final Data Backend Decision

## Summary

- Schema: `autovla.zjh_backend_bakeoff.v1`
- Subset fingerprint: `c7399785ff774edb89d4af8b09173d98f2c0791a587bf8d00f45e49b1e0fa40f`
- Fair comparison worker_count=8 required: `True`
- W8 evidence is integrated; no converted backend winner is selected.
- Primary worker_count=8 WebDataset evidence is present and `primary_worker_count_satisfied=true`.
- Format-native loader W8 evidence is present for `webdataset_converted` and `robodm_style_converted`; detailed task evidence is under `runs/tmp/AUTOVLA-M3-NATIVE-LOADER-W8-EXECUTION-001/`.
- `robodm_style_converted` is an owned native bounded prototype, not actual Robo-DM.
- WebDataset read remains `INSUFFICIENT_TELEMETRY` because raw comparator fields were not stitched into the read report; comparator_valid=true and checksum validation passed.
- Raw telemetry dry-run remains the next adjudication step.
- Final decision class: `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`.
- Next action: continue raw telemetry dry-run via `AUTOVLA-M3-GR00T-N1D6-RAWPATH-FINETUNE-TELEMETRY-DRYRUN-001` before any final winner, fine-tune, or training-format claim.
- No converted backend is selected as winner because no full raw-comparable converted winner exists.
- WebDataset backend decision status: `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`.
- No real training, model load, checkpoint read, tokenizer load, W&B/HF network, endpoint, or robot action.

## Candidate Dashboard

| Candidate | Dependency status | Worker count | Batch size | Sample count | Build time | Artifact size | P50 latency | P95 latency | Samples/sec | File opens | PFS read MB/s | Estimated GPU wait | Status | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `zjh_lerobot_v21_raw` | `no_new_dependency` | `8` | `missing` | `512` | `not_applicable` | `missing` | `1.992976` | `1.992976` | `256902.240669` | `12` | `not_applicable` | `0.0` | `FAIL` | build a PFS-backed Training Store before training |
| `lerobot_v3_view` | `official_lerobot_v3_dependency_not_approved` | `8` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `NOT_RUN_DEPENDENCY_BLOCKED` | official LeRobot v3 route is dependency-blocked; no native prototype is selected as a final backend |
| `robodm_style_container` | `actual_robodm_dependency_license_blocked` | `8` | `missing` | `512` | `49.798713` | `missing` | `9.264098` | `9.264098` | `55267.118288` | `6` | `47.125842` | `0.0` | `INSUFFICIENT_TELEMETRY` | run bounded raw decode and store-read benchmark in one compute evidence pass |
| `webdataset_streaming` | `webdataset_dependency_approved_pr18` | `8` | `missing` | `512` | `592.675342` | `missing` | `348.007695` | `348.007695` | `1471.231836` | `6` | `8.768431` | `0.0` | `INSUFFICIENT_TELEMETRY` | primary worker_count=8 WebDataset evidence is integrated; no converted backend winner is selected; continue raw telemetry dry-run |
| `zarr_chunked_store` | `actual_zarr_python310_version_decision_missing` | `8` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `NOT_RUN_DEPENDENCY_BLOCKED` | actual Zarr route is dependency/version-blocked; no native prototype is selected as a final backend |
| `gr00t_original_dataloader` | `model_training_side_effect_safety_not_proven` | `8` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `NOT_RUN_UNSAFE_OR_UNAVAILABLE` | do not execute until Model and Training prove dataloader-only safety |

## Final Decision

- Final decision class: `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`.
- Next action: continue raw telemetry dry-run via `AUTOVLA-M3-GR00T-N1D6-RAWPATH-FINETUNE-TELEMETRY-DRYRUN-001` before any final winner, fine-tune, or training-format claim.
- No converted backend winner is selected; continue raw telemetry dry-run before any backend choice.
- WebDataset W8/native evidence is decision-support evidence, not a winner selection.
- Native-loader W8 evidence for `webdataset_converted` and `robodm_style_converted` is decision-support evidence, not a winner selection.
- Raw W8 evidence remains a baseline, not fine-tune readiness.
- Robo-DM-style evidence is a native bounded prototype; actual Robo-DM remains dependency/license-blocked.
- LeRobot v3 and Zarr remain `NOT_RUN_DEPENDENCY_BLOCKED`.
- GR00T original dataloader remains `NOT_RUN_UNSAFE_OR_UNAVAILABLE`.

## Shared Subset/Window Policy

- All benchmarkable rows must use the same ordered `training_window_ids` manifest.
- Raw ZJH fields are action=`action`, state=`observation.state`, and three declared camera refs.
- Candidates without action/state/action_mask equivalence stay out of speed ranking.
- Prototype rows are decision-support only and must not be named as official dependency backends.

## Residual Compute Requirement

- Current evidence includes raw bounded-decode, native bounded container-cache prototype, and WebDataset package-backed streaming rows where available.
- Final acceptance continues through raw telemetry dry-run; this dashboard does not select a final training-store winner or training format.
- W8 WebDataset evidence is primary-comparable only when `primary_worker_count_satisfied=true`.

## Publication Notes

- `zjh_lerobot_v21_raw` is the no-new-dependency raw baseline.
- `prototype_only` rows are native metadata/report scaffolds, not official backend claims.
- Dependency-backed official routes remain blocked until their exact dependency gates pass.
- Generated store/media/checkpoint/model artifacts must stay out of git.
