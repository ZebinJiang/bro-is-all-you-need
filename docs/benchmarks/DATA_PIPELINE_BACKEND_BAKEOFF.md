# AutoVLA ZJH Data Backend Bakeoff

## Summary

- Schema: `autovla.zjh_backend_bakeoff.v1`
- Subset fingerprint: `37b653117da3a7f9e7aa27a65b22d9a0c77a4515113ad6ce552a518cf8dfd346`
- Fair comparison worker_count=8 required: `True`
- Partial compute evidence is integrated; final winner remains pending.
- Primary worker_count=8 WebDataset evidence is present and `primary_worker_count_satisfied=true`.
- WebDataset read remains `INSUFFICIENT_TELEMETRY` because raw comparator fields were not stitched into the read report; comparator_valid=true and checksum validation passed.
- Missing final requirements: final winner, Owner reviews, draft PR.
- WebDataset backend decision status: `READY_FOR_USER_DECISION_BACKEND`.
- No real training, model load, checkpoint read, tokenizer load, W&B/HF network, endpoint, or robot action.

## Candidate Dashboard

| Candidate | Dependency status | Worker count | Batch size | Sample count | Build time | Artifact size | P50 latency | P95 latency | Samples/sec | File opens | PFS read MB/s | Estimated GPU wait | Status | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `zjh_lerobot_v21_raw` | `no_new_dependency` | `8` | `missing` | `512` | `not_applicable` | `missing` | `1.992976` | `1.992976` | `256902.240669` | `12` | `not_applicable` | `0.0` | `FAIL` | build a PFS-backed Training Store before training |
| `lerobot_v3_view` | `official_lerobot_v3_dependency_not_approved` | `8` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `NOT_RUN_PROTOTYPE_ONLY` | official LeRobot v3 route is dependency-blocked; local row is prototype_only |
| `robodm_style_container` | `actual_robodm_dependency_license_blocked` | `8` | `missing` | `512` | `49.798713` | `missing` | `9.264098` | `9.264098` | `55267.118288` | `6` | `47.125842` | `0.0` | `INSUFFICIENT_TELEMETRY` | run bounded raw decode and store-read benchmark in one compute evidence pass |
| `webdataset_streaming` | `webdataset_dependency_approved_pr18` | `8` | `missing` | `512` | `592.675342` | `missing` | `348.007695` | `348.007695` | `1471.231836` | `6` | `8.768431` | `0.0` | `INSUFFICIENT_TELEMETRY` | primary worker_count=8 WebDataset evidence is integrated; final backend winner still requires Manager/user decision |
| `zarr_chunked_store` | `actual_zarr_python310_version_decision_missing` | `8` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `NOT_RUN_PROTOTYPE_ONLY` | actual Zarr route is dependency/version-blocked; local row is prototype_only |
| `gr00t_original_dataloader` | `model_training_side_effect_safety_not_proven` | `8` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `NOT_RUN_UNSAFE_OR_UNAVAILABLE` | do not execute until Model and Training prove dataloader-only safety |

## Shared Subset/Window Policy

- All benchmarkable rows must use the same ordered `training_window_ids` manifest.
- Raw ZJH fields are action=`action`, state=`observation.state`, and three declared camera refs.
- Candidates without action/state/action_mask equivalence stay out of speed ranking.
- Prototype rows are decision-support only and must not be named as official dependency backends.

## Residual Compute Requirement

- Current evidence includes raw bounded-decode, native bounded container-cache prototype, and WebDataset package-backed streaming rows where available.
- Final acceptance still requires Manager/user backend decision; this dashboard does not select a final training-store winner.
- W8 WebDataset evidence is primary-comparable only when `primary_worker_count_satisfied=true`.

## Publication Notes

- `zjh_lerobot_v21_raw` is the no-new-dependency raw baseline.
- `prototype_only` rows are native metadata/report scaffolds, not official backend claims.
- Dependency-backed official routes remain blocked until their exact dependency gates pass.
- Generated store/media/checkpoint/model artifacts must stay out of git.
